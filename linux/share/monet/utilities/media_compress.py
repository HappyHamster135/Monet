"""Inspect local media and encode a private output before the UI publishes it."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from actions import tr


def output_suffix(path):
    suffix = path.suffix.lower()
    return {".jpeg": ".jpg", ".heif": ".heic"}.get(suffix, suffix)


def qt_reader(path):
    from PySide6.QtGui import QImageReader
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    return reader


def native_picture(path):
    # These still-image containers can also be identified as single-frame
    # movies by FFmpeg. Use the desktop image reader when Pillow lacks them.
    with path.open("rb") as file:
        header = file.read(32)
    return (path.suffix.lower() in (".heif", ".heic", ".avif", ".jxl") or header[:2] == b"\xff\x0a"
            or (header[4:8] == b"ftyp" and header[8:12] in (b"heic", b"heix", b"hevc", b"mif1", b"avif", b"avis")))


def source_signature(path):
    st = path.stat()
    return [st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size]


def inspect_file(path):
    from PIL import Image, UnidentifiedImageError
    if not path.is_file():
        raise ValueError(tr("Choose a local media file."))
    signature = source_signature(path)
    info = {"size": signature[-1], "signature": signature, "audio": 0, "duration": 0, "loop": 0}
    try:
        picture = Image.open(path)
    except Image.DecompressionBombError as error:
        raise ValueError(tr("This picture is too large to process.")) from error
    except UnidentifiedImageError:
        picture = None
        if native_picture(path):
            reader = qt_reader(path)
            if reader.canRead() and reader.size().isValid():
                size = reader.size()
                if reader.transformation().value & 4:
                    size.transpose()
                info.update(kind="image", format=bytes(reader.format()).decode().upper(), reader="qt",
                            width=size.width(), height=size.height())
                if not reader.supportsAnimation() or reader.imageCount() == 1:
                    return info
                info["kind"] = "animation"
    if picture:
        with picture:
            info["format"] = picture.format
            info["width"], info["height"] = picture.size
            if picture.getexif().get(274) in (5, 6, 7, 8):
                info["width"], info["height"] = picture.height, picture.width
            info["loop"] = picture.info.get("loop", -1)
            info["kind"] = "animation" if getattr(picture, "is_animated", False) else "image"
            if info["kind"] == "image":
                return info
    result = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                             "-show_entries", "format=duration:format_tags=major_brand:stream=index,codec_type,codec_name,pix_fmt,width,height,duration:"
                             "stream_disposition=attached_pic:stream_side_data=rotation",
                             "-of", "json", str(path)], capture_output=True, timeout=45)
    if result.returncode:
        raise ValueError(tr("This file has no readable picture or video."))
    probe = json.loads(result.stdout)
    streams = probe.get("streams", [])
    video = next((s for s in streams if s["codec_type"] == "video" and
                  not s.get("disposition", {}).get("attached_pic") and s.get("width") and s.get("height")), None)
    if not video:
        raise ValueError(tr("This file has no readable picture or video."))
    if "kind" not in info:
        info.update(kind="video", width=video["width"], height=video["height"])
        if any(abs(float(side.get("rotation", 0))) % 180 == 90 for side in video.get("side_data_list", [])):
            info["width"], info["height"] = info["height"], info["width"]
    info["stream"] = video["index"]
    info["audio"] = sum(s["codec_type"] == "audio" for s in streams)
    # Skip lossy recompression only for a compatible MP4. QuickTime files and
    # other containers can also carry H.264 and AAC under an .mp4 filename.
    brand = probe.get("format", {}).get("tags", {}).get("major_brand", "").strip()
    info["compatible_mp4"] = (brand in ("isom", "iso2", "iso3", "iso4", "iso5", "iso6", "avc1", "mp41", "mp42", "M4V")
                              and video.get("codec_name") == "h264" and video.get("pix_fmt") == "yuv420p"
                              and all(s is video or (s["codec_type"] == "audio" and s.get("codec_name") == "aac")
                                      for s in streams))
    try:
        duration = float(probe.get("format", {}).get("duration") or video.get("duration") or 0)
        info["duration"] = duration if math.isfinite(duration) and duration > 0 else 0
    except ValueError:
        pass
    return info


def dimensions(width, height, edge):
    ratio = min(1, edge / max(width, height)) if edge else 1
    return max(1, round(width * ratio)), max(1, round(height * ratio))


def encode_video(source, output, info, options, progress):
    quality, edge, limit, audio = options
    count = info["audio"] if audio else 0
    duration = info["duration"]
    if limit and not duration and info["kind"] == "animation":
        # APNG and animated WebP often expose packet times without a container duration.
        with subprocess.Popen(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams",
                               "v:0", "-show_entries", "packet=duration_time", "-of", "csv=p=0", str(source)],
                              stdout=subprocess.PIPE) as probe:
            for packet in probe.stdout:
                try:
                    duration += max(0, float(packet.strip()))
                except ValueError:
                    continue
            if probe.wait():
                duration = 0
    if info["kind"] == "image":
        duration = 1 / 25
    width, height = dimensions(info["width"], info["height"], edge)
    # Use even dimensions for H.264 and carry the input display aspect through the scale.
    width, height = max(2, width - width % 2), max(2, height - height % 2)
    scale = f"scale={width}:{height}"
    base = ffmpeg(source) + ["-map", f"0:{info.get('stream', 0)}", "-vf", scale, "-c:v", "libx264",
                             "-preset", "veryfast", "-pix_fmt", "yuv420p", "-threads", "2"]
    sound = ["-map", "0:a?", "-c:a", "aac"] if count else ["-an"]
    if not limit or info["size"] <= limit:
        transcode(base + ["-crf", str((29, 24, 19)[quality])] + sound +
                  ["-movflags", "+faststart", str(output)], duration, progress)
        if not limit or output.stat().st_size <= limit:
            return width, height
    if not duration:
        raise ValueError(tr("This video needs a known duration to fit a size limit."))
    # Reserve room for MP4 headers and AAC variation. Check the actual file after encoding.
    budget = int((limit - 4096) * 8 * .96 / duration)
    audio_rate = min(128000, max(16000, budget // (5 * max(1, count))))
    rate = budget - count * audio_rate
    if count:
        sound += ["-b:a", str(audio_rate)]
    for attempt in range(2):
        if rate < 12000:
            break
        pass_args = ["-b:v", str(rate), "-passlogfile", str(output.parent / "video-pass")]
        for number in (1, 2):
            args = ["-an", "-f", "null", "/dev/null"] if number == 1 else sound + ["-movflags", "+faststart", str(output)]
            def update(fraction):
                progress(((number-1) + fraction) / 2)
            transcode(base + pass_args + ["-pass", str(number)] + args, duration, update)
        actual = output.stat().st_size
        if actual <= limit:
            return width, height
        rate = int(rate - (actual-limit) * 8 / duration - rate * .08)
    raise ValueError(tr("The file could not fit this limit. Choose a larger size or a shorter clip."))


def ffmpeg(source):
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-stats_period", "0.25",
            "-progress", "pipe:1", "-nostats", "-threads", "2", "-filter_threads", "1",
            "-filter_complex_threads", "1", "-protocol_whitelist", "file,pipe", "-i", str(source)]


def transcode(command, duration, progress):
    with tempfile.TemporaryFile() as errors:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors) as proc:
            for line in proc.stdout:
                if duration and line.startswith(b"out_time_us="):
                    try:
                        fraction = int(line[12:]) / (duration * 1000000)
                    except ValueError:
                        continue
                    progress(min(1, max(0, fraction)))
            if proc.wait():
                errors.seek(max(0, errors.tell()-900))
                detail = errors.read().decode(errors="replace").strip().splitlines()
                raise ValueError(detail[-1] if detail else tr("The media encoder could not finish."))


def encode_gif(source, output, info, quality, edge, limit, progress):
    video = info["kind"] == "video"
    width, height = dimensions(info["width"], info["height"], edge or (720 if video else 0))
    colors = (96, 192, 256)[quality]
    fps = (10, 15, 24)[quality]
    for _ in range(6):
        filters = (f"fps={fps}," if video else "") + f"scale={width}:{height}:flags=lanczos,split[a][b]"
        graph = (f"[0:{info.get('stream', 0)}]{filters};[a]palettegen=max_colors={colors}:stats_mode=single[p];"
                 "[b][p]paletteuse=new=1:dither=bayer[v]")
        transcode(ffmpeg(source) + ["-filter_complex", graph, "-map", "[v]", "-an", "-fps_mode", "passthrough",
                                    "-loop", str(info["loop"]), "-threads", "2", str(output)],
                  info["duration"], progress)
        actual = output.stat().st_size
        if not limit or actual <= limit:
            return width, height
        factor = min(.85, .94 * math.sqrt(limit / actual))
        width, height = dimensions(width, height, max(1, int(max(width, height) * factor)))
        if video:
            fps = max(4, int(fps * .85))
    raise ValueError(tr("The animation could not fit this limit. Try a larger size."))


def encode_picture(source, output, info, quality, edge, limit, preview=False):
    from PIL import Image, ImageOps
    from picture_edit import frame_picture, picture_geometry, watermark
    options = info.get("picture_options", {})
    full_size = picture_geometry((info["width"], info["height"]), options, edge)
    width, height = dimensions(*full_size, 440) if preview else full_size
    if info["kind"] == "video":
        still = output.parent / "frame.png"
        transcode(ffmpeg(source) + ["-map", f"0:{info['stream']}", "-frames:v", "1", "-threads", "1", str(still)],
                  0, lambda _: None)
        source = still
    if info.get("reader") == "qt":
        from PySide6.QtGui import QImage
        reader = qt_reader(source)
        native = reader.read()
        if native.isNull():
            raise ValueError(reader.errorString())
        transparent = native.hasAlphaChannel()
        native = native.convertToFormat(QImage.Format_RGBA8888 if transparent else QImage.Format_RGB888)
        mode = "RGBA" if transparent else "RGB"
        profile = bytes(native.colorSpace().iccProfile()) or None
        picture = Image.frombytes(mode, (native.width(), native.height()), native.constBits(),
                                  "raw", mode, native.bytesPerLine(), 1)
    else:
        with Image.open(source) as image:
            if image.format == "JPEG" and (edge or options.get("size") or preview):
                image.draft(image.mode, (max(width, height),) * 2)
            picture = ImageOps.exif_transpose(image)
            profile = image.info.get("icc_profile") if image.mode in ("RGB", "RGBA") else None
            transparent = "A" in picture.getbands() or "transparency" in picture.info
            picture = picture.convert("RGBA" if transparent else "RGB")
    initial_quality = (62, 80, 93)[quality]
    frame = None
    for _ in range(8):
        if frame is None or frame.size != (width, height):
            frame = frame_picture(picture, (width, height), options)
            frame = watermark(frame, options, min(width / full_size[0], height / full_size[1]))
            fill = options.get("background") or ("white" if output_suffix(output) in (".jpg", ".pdf") else None)
            if fill and frame.mode == "RGBA":
                background = Image.new("RGB", frame.size, fill)
                background.paste(frame, mask=frame.getchannel("A"))
                frame = background
            if options.get("strip_metadata"):
                # Pillow can carry input tags through copies and resize operations.
                frame.info.clear()
        if preview:
            frame.save(output, format="PNG")
            return
        args = {"icc_profile": profile} if profile else {}
        if output_suffix(output) == ".png":
            args["compress_level"] = 7
        else:
            args["quality"] = initial_quality
        if output_suffix(output) == ".heic":
            from PySide6.QtGui import QColorSpace, QImage, QImageWriter
            data = frame.tobytes()
            alpha = frame.mode == "RGBA"
            native = QImage(data, width, height, width * (4 if alpha else 3),
                            QImage.Format_RGBA8888 if alpha else QImage.Format_RGB888)
            if profile:
                native.setColorSpace(QColorSpace.fromIccProfile(profile))
            writer = QImageWriter(str(output), b"heic")
            writer.setQuality(initial_quality)
            if not writer.write(native):
                raise ValueError(writer.errorString())
        else:
            frame.save(output, **args)
        actual = output.stat().st_size
        if not limit or actual <= limit:
            return width, height
        if options.get("size"):
            if output_suffix(output) == ".png" or initial_quality <= 12:
                break
            initial_quality = max(12, min(initial_quality - 10, round(initial_quality * limit / actual)))
            continue
        factor = min(.85, .94 * math.sqrt(limit / actual))
        width, height = dimensions(width, height, max(1, int(max(width, height) * factor)))
    raise ValueError(tr("The picture could not fit this limit. Try a larger size."))


def main(argv):
    if argv[0] == "inspect":
        for filename in json.load(sys.stdin):
            try:
                info = inspect_file(Path(filename))
                result = [filename, info, ""]
            except (OSError, EOFError, SyntaxError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                result = [filename, None, str(error)]
            print(json.dumps(result), flush=True)
        return
    source = Path(argv[1])
    if argv[-1] == "--source-info":
        info = json.load(sys.stdin)
        argv = argv[:-1]
        if source_signature(source) != info["signature"]:
            raise ValueError(tr("The source changed. Review the file and save again."))
    else:
        info = inspect_file(source)
    output = Path(argv[2])
    quality, edge, limit, audio = map(int, argv[3:])
    if quality not in (0, 1, 2) or edge < 0 or limit < 0 or audio not in (0, 1):
        raise ValueError("Invalid encoding options")
    def progress(fraction):
        print(min(99, round(fraction*100)), flush=True)
    suffix = output_suffix(output)
    if suffix == ".heic" or info.get("reader") == "qt":
        # The native HEIC plugin chooses its own thread pool. Bound the worker,
        # leaving the desktop schedulable while saving a large camera photo.
        allowed = sorted(os.sched_getaffinity(0))
        try:
            os.sched_setaffinity(0, allowed[:max(1, min(2, len(allowed)//2))])
        except PermissionError:
            pass
    same_picture_format = (info.get("format") == {".jpg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".gif": "GIF",
                                                  ".heic": "HEIC"}.get(suffix)
                           and (info["kind"] == "image" or (info["kind"] == "animation" and suffix == ".gif")))
    same_video_format = suffix == ".mp4" and info.get("compatible_mp4") and (audio or not info["audio"])
    original_fits = ((same_picture_format or same_video_format) and (not edge or max(info["width"], info["height"]) <= edge)
                     and (not limit or info["size"] <= limit))
    if argv[0] == "preview":
        encode_picture(source, output, info, quality, edge, 0, preview=True)
        return
    if info.get("picture_options", {}).keys() - {"keep_date"} and suffix not in (".mp4", ".gif"):
        original_fits = False
    size = info["width"], info["height"]
    if original_fits and limit:
        shutil.copyfile(source, output)
    elif suffix == ".mp4":
        size = encode_video(source, output, info, (quality, edge, limit, audio), progress)
    elif suffix == ".gif":
        size = encode_gif(source, output, info, quality, edge, limit, progress)
    elif suffix in (".jpg", ".webp", ".png", ".heic", ".pdf"):
        size = encode_picture(source, output, info, quality, edge, limit)
    else:
        raise ValueError("Unknown output format")
    if original_fits and not limit and output.stat().st_size > info["size"]:
        shutil.copyfile(source, output)
        size = info["width"], info["height"]
    if info.get("report_dimensions"):
        print(json.dumps(size), flush=True)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, EOFError, SyntaxError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
