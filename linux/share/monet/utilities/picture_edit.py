"""Picture framing and watermark placement shared by preview and export."""
from pathlib import Path

from actions import tr


def picture_geometry(source_size, options, edge):
    width, height = source_size
    mode = options.get("size", "")
    if mode == "width":
        width = options["width"]
        height = max(1, round(source_size[1] * width / source_size[0]))
    elif mode == "height":
        height = options["height"]
        width = max(1, round(source_size[0] * height / source_size[1]))
    elif mode == "exact":
        width, height = options["width"], options["height"]
    elif edge and max(width, height) > edge:
        ratio = edge / max(width, height)
        width, height = max(1, round(width * ratio)), max(1, round(height * ratio))
    if min(width, height) < 1 or (mode and (max(width, height) > 32768 or width * height > 48000000)):
        raise ValueError(tr("Choose picture dimensions under 48 megapixels and 32,768 pixels per side."))
    return width, height


def contain(image, box):
    from PIL import Image
    scale = min(box[0] / image.width, box[1] / image.height)
    size = max(1, round(image.width * scale)), max(1, round(image.height * scale))
    return image if size == image.size else image.resize(size, Image.Resampling.LANCZOS)


def frame_picture(picture, size, options):
    from PIL import Image, ImageOps
    if options.get("size") == "exact" and options.get("framing") == "fill":
        return ImageOps.fit(picture, size, Image.Resampling.LANCZOS)
    if options.get("size") == "exact" and options.get("framing") == "fit":
        fitted = contain(picture, size)
        background = Image.new("RGBA", size)
        background.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
        return background
    return picture if picture.size == size else picture.resize(size, Image.Resampling.LANCZOS)


def read_logo(path, box):
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(path) as image:
            if image.format == "JPEG":
                image.draft(image.mode, (max(box), max(box)))
            return contain(ImageOps.exif_transpose(image).convert("RGBA"), box)
    except Image.DecompressionBombError as error:
        raise ValueError(tr("This picture is too large to process.")) from error
    except UnidentifiedImageError:
        # Qt can render SVG logos at the intended resolution as well as HEIC.
        from PySide6.QtCore import QSize, Qt
        import os
        from PySide6.QtGui import QGuiApplication, QImage, QImageReader
        # SVG text uses Qt's font database even when rendering to an image.
        app = QGuiApplication.instance()
        if app is None:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
            app = QGuiApplication([])
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if not size.isValid() or size.isEmpty():
            raise ValueError(tr("Choose an available watermark image."))
        reader.setScaledSize(size.scaled(QSize(*box), Qt.KeepAspectRatio).expandedTo(QSize(1, 1)))
        result = reader.read()
        if result.isNull():
            raise ValueError(reader.errorString())
        result = result.convertToFormat(QImage.Format_RGBA8888)
        image = Image.frombytes("RGBA", (result.width(), result.height()), result.constBits(),
                                "raw", "RGBA", result.bytesPerLine(), 1)
        return contain(image, box)


def watermark(frame, options, margin_factor):
    from PIL import Image, ImageDraw, ImageFont
    text = options.get("text", "").strip()
    logo = options.get("logo", "")
    if not text and not logo:
        return frame
    side = min(frame.size)
    margin = min(max(0, (side - 1) // 2), round(options.get("margin", 16) * margin_factor))
    available_w = max(1, frame.width - 2 * margin)
    available_h = max(1, frame.height - 2 * margin)
    width = min(available_w, max(1, round(frame.width * options.get("scale", 25) / 100)))
    layers = []
    if logo:
        layers.append(read_logo(Path(logo), (width, available_h)))
    if text:
        # Draw in a small buffer, then fit it to the requested proportion of the picture.
        try:
            font = ImageFont.truetype("NotoSans-Regular.ttf", 96)
        except OSError:
            font = ImageFont.load_default(size=96)
        left, top, right, bottom = font.getbbox(text, stroke_width=2)
        label = Image.new("RGBA", (max(1, right-left), max(1, bottom-top)))
        ImageDraw.Draw(label).text((-left, -top), text, font=font, fill="white",
                                   stroke_width=2, stroke_fill=(0, 0, 0, 190))
        layers.append(contain(label, (width, available_h)))
    gap = max(1, round(min(width, available_h) * .04)) if len(layers) > 1 else 0
    mark = Image.new("RGBA", (max(layer.width for layer in layers), sum(layer.height for layer in layers) + gap))
    y = 0
    for layer in layers:
        mark.paste(layer, ((mark.width-layer.width)//2, y))
        y += layer.height + gap
    mark.thumbnail((available_w, available_h), Image.Resampling.LANCZOS)
    alpha = options.get("opacity", 55) / 100
    mark.putalpha(mark.getchannel("A").point(lambda v: round(v * alpha)))
    if frame.mode != "RGBA":
        frame = frame.convert("RGBA")
    else:
        frame = frame.copy()
    position = options.get("position", "bottom-right")
    if position == "center":
        x, y = (frame.width-mark.width)//2, (frame.height-mark.height)//2
    else:
        x = margin if position.endswith("left") else frame.width - mark.width - margin
        y = margin if position.startswith("top") else frame.height - mark.height - margin
    frame.alpha_composite(mark, (x, y))
    return frame
