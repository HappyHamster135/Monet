"""Export an edited local recording to a new file beside its temporary output."""
import ctypes
import errno
import os
from pathlib import Path
import tempfile


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


def export_command(source, output, start, end, speed, crop, mute):
    if not 0 <= start < end or speed not in (0.5, 1, 1.5, 2):
        raise ValueError("Invalid trim range or playback speed")
    filters = []
    if crop:
        x, y, w, h = crop
        if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1.000001-x and 0 < h <= 1.000001-y):
            raise ValueError("Crop is outside the picture")
        filters.append(f"crop=w='max(2,trunc(iw*{w:.8f}/2)*2)':h='max(2,trunc(ih*{h:.8f}/2)*2)':"
                       f"x='trunc(iw*{x:.8f}/2)*2':y='trunc(ih*{y:.8f}/2)*2'")
    if speed != 1:
        filters.append(f"setpts=PTS/{speed:g}")
    command = ["nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
               "-progress", "pipe:1", "-nostats", "-filter_threads", "1", "-filter_complex_threads", "1",
               "-ss", f"{start/1000:.3f}", "-t", f"{(end-start)/1000:.3f}", "-threads", "2",
               "-protocol_whitelist", "file,pipe", "-i", str(source), "-map_metadata", "-1", "-map_chapters", "-1"]
    if output.suffix.lower() == ".gif":
        # A palette per frame keeps memory bounded even for long captures.
        filters += ["fps=12", "scale='min(800,iw)':-1:flags=lanczos", "split[a][b]"]
        graph = "[0:v:0]" + ",".join(filters) + ";[a]palettegen=stats_mode=single[p];[b][p]paletteuse=new=1:dither=bayer[v]"
        command += ["-filter_complex", graph, "-map", "[v]", "-an", "-loop", "0"]
    elif output.suffix.lower() == ".mp4":
        filters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")
        command += ["-map", "0:v:0", "-vf", ",".join(filters), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        if mute:
            command += ["-an"]
        else:
            command += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "160k"]
            if speed != 1:
                command += ["-af", f"atempo={speed:g}"]
    else:
        raise ValueError("Unknown export format")
    return command + ["-threads", "2", str(output)]
