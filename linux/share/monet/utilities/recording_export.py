"""Export an edited local recording to a new file beside its temporary output."""
from dataclasses import dataclass
import ctypes
import errno
import os
from pathlib import Path
import tempfile

from recording_zoom import zoom_filters


class ExportFile:
    def __init__(self, destination):
        self.destination = Path(destination)
        if os.path.lexists(self.destination):
            raise FileExistsError(self.destination)
        self.directory = tempfile.TemporaryDirectory(prefix=".monet-recording-", dir=self.destination.parent)
        self.file = Path(self.directory.name) / ("export" + self.destination.suffix)

    def publish(self):
        # Both paths are on the same filesystem. RENAME_NOREPLACE also works
        # on removable filesystems that cannot create a hard link.
        try:
            rename = ctypes.CDLL(None, use_errno=True).renameat2
        except AttributeError:
            rename = None
        if rename is not None:
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            if rename(-100, os.fsencode(self.file), -100, os.fsencode(self.destination), 1) == 0:
                return
            code = ctypes.get_errno()
            if code not in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
                raise OSError(code, os.strerror(code), self.destination)
        os.link(self.file, self.destination)

    def close(self):
        self.directory.cleanup()


@dataclass(frozen=True)
class ExportLayer:
    box: tuple
    start: int
    end: int
    image: Path | None
    sigma: float


def overlay_graph(command, layers, start, end, base):
    graph = []
    image_index = 0
    for i, layer in enumerate(layers):
        if layer.end <= start or layer.start >= end:
            continue
        x, y, w, h = layer.box
        if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1.000001-x and 0 < h <= 1.000001-y):
            raise ValueError("Overlay outside the picture")
        on = f"gte(t,{max(0,layer.start-start)/1000:.3f})*lt(t,{(min(end,layer.end)-start)/1000:.3f})"
        graph.append(f"{base}split[under{i}][ref{i}]")
        if layer.image is not None:
            image_index += 1
            command.extend(["-threads", "1", "-f", "image2", "-pattern_type", "none", "-i", str(layer.image)])
            graph.append(f"[{image_index}:v][ref{i}]scale=w='max(1,round(rw*{w:.8f}))':"
                         f"h='max(1,round(rh*{h:.8f}))':eval=init[art{i}]")
        else:
            graph.append(f"[ref{i}]crop=w='max(1,round(iw*{w:.8f}))':h='max(1,round(ih*{h:.8f}))':"
                         f"x='round(iw*{x:.8f})':y='round(ih*{y:.8f})':exact=1,"
                         f"gblur=sigma={layer.sigma:.4f}:steps=2:enable='{on}'[art{i}]")
        base = f"[layer{i}]"
        graph.append(f"[under{i}][art{i}]overlay=x='round(W*{x:.8f})':y='round(H*{y:.8f})':"
                     f"format=yuv444:enable='{on}'{base}")
    return graph, base


def export_command(source, output, start, end, speed, crop, mute, layers=(), zooms=(), size=(0, 0), fps=0):
    if not 0 <= start < end or speed not in (0.5, 1, 1.5, 2):
        raise ValueError("Invalid trim range or playback speed")
    filters = []
    if crop:
        x, y, w, h = crop
        if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1.000001-x and 0 < h <= 1.000001-y):
            raise ValueError("Crop is outside the picture")
        filters.append(f"crop=w='max(2,trunc(iw*{w:.8f}/2)*2)':h='max(2,trunc(ih*{h:.8f}/2)*2)':"
                       f"x='trunc(iw*{x:.8f}/2)*2':y='trunc(ih*{y:.8f}/2)*2'")
    rate, motion = zoom_filters(zooms, start, end, size, crop, fps)
    filters.extend(motion)
    if speed != 1:
        filters.append(f"setpts=PTS/{speed:g}")
    command = ["nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
               "-progress", "pipe:1", "-nostats", "-filter_threads", "1", "-filter_complex_threads", "1",
               "-ss", f"{start/1000:.3f}"]
    duration = (end-start)/1000
    # Keep the last decoded frame before a trim inside a long still. The FPS
    # filter selects that frame at time zero and drives overlays as it moves.
    command += ["-noaccurate_seek"] if rate else ["-t", f"{duration:.3f}"]
    command += ["-threads", "2", "-protocol_whitelist", "file,pipe", "-i", str(source)]
    graph, base = overlay_graph(command, layers, start, end, "[clock]" if rate else "[0:v:0]")
    if rate:
        graph.insert(0, f"[0:v:0]fps={rate}:start_time=0,trim=duration={duration:.3f}[clock]")
    command += ["-map_metadata", "-1", "-map_chapters", "-1"]
    if output.suffix.lower() == ".gif":
        # A palette per frame keeps memory bounded even for long captures.
        filters += ["fps=12", "scale='min(800,iw)':-1:flags=lanczos", "split[a][b]"]
        graph.append(base + ",".join(filters) + ";[a]palettegen=stats_mode=single[p];[b][p]paletteuse=new=1:dither=bayer[v]")
        command += ["-filter_complex", ";".join(graph), "-map", "[v]", "-an", "-loop", "0"]
    elif output.suffix.lower() == ".mp4":
        filters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")
        if graph:
            graph.append(base + ",".join(filters) + "[v]")
            command += ["-filter_complex", ";".join(graph), "-map", "[v]"]
        else:
            command += ["-map", "0:v:0", "-vf", ",".join(filters)]
        if speed != 1:
            command += ["-fps_mode", "vfr", "-enc_time_base:v", "filter"]
        command += ["-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        if mute:
            command += ["-an"]
        else:
            command += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "160k"]
            audio = [f"atrim=start=0:end={duration:.3f}"] if rate else []
            if speed != 1:
                audio.append(f"atempo={speed:g}")
            if audio:
                command += ["-af", ",".join(audio)]
    else:
        raise ValueError("Unknown export format")
    if rate:
        command += ["-t", f"{duration/speed:.6f}"]
    return command + ["-threads", "2", str(output)]
