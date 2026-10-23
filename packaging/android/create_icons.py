"""Generate the branded Android launcher icon from the canonical NJA mark."""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "static" / "icon-512.png"
RES = Path(__file__).resolve().parent / "app" / "src" / "main" / "res"


def logo_crop():
    source = Image.open(SOURCE).convert("RGBA")
    difference = ImageChops.difference(source.convert("RGB"), Image.new("RGB", source.size, "white"))
    mask = difference.convert("L").point(lambda value: 255 if value > 12 else 0)
    return source.crop(mask.getbbox())


def gradient(size):
    image = Image.new("RGBA", (size, size))
    pixels = image.load()
    start, middle, end = (16, 65, 222), (2, 139, 216), (38, 218, 235)
    for y in range(size):
        for x in range(size):
            position = (x + y) / (2 * (size - 1))
            left, right, local = (start, middle, position * 2) if position < .5 else (middle, end, (position - .5) * 2)
            pixels[x, y] = tuple(round(left[i] + (right[i] - left[i]) * local) for i in range(3)) + (255,)
    overlay = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((-size * .3, -size * .42, size * .72, size * .6), fill=(255, 255, 255, 27))
    draw.ellipse((size * .38, size * .52, size * 1.2, size * 1.25), fill=(0, 26, 102, 35))
    for offset in range(-size, size * 2, max(18, size // 13)):
        draw.line((offset, 0, offset - size, size), fill=(255, 255, 255, 9), width=max(1, size // 180))
    return Image.alpha_composite(image, overlay)


def place_mark(canvas, box):
    shadow = Image.new("RGBA", canvas.size)
    ImageDraw.Draw(shadow).rounded_rectangle(box, radius=(box[2] - box[0]) // 4, fill=(0, 24, 76, 125))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(5, canvas.width // 34)))
    canvas.alpha_composite(shadow, (0, canvas.width // 42))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=(box[2] - box[0]) // 4, fill=(255, 255, 255, 242), outline=(255, 255, 255, 205), width=max(2, canvas.width // 128))
    mark = logo_crop()
    available = int((box[2] - box[0]) * .78)
    mark.thumbnail((available, available), Image.Resampling.LANCZOS)
    x = (canvas.width - mark.width) // 2
    y = (canvas.height - mark.height) // 2
    canvas.alpha_composite(mark, (x, y))


def complete_icon(size):
    icon = gradient(size)
    margin = round(size * .145)
    place_mark(icon, (margin, margin, size - margin, size - margin))
    return icon


def main():
    preview = complete_icon(512)
    preview.save(Path(__file__).resolve().parent / "icon-source.png")
    densities = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    for folder, size in densities.items():
        target = RES / folder
        target.mkdir(parents=True, exist_ok=True)
        icon = preview.resize((size, size), Image.Resampling.LANCZOS)
        icon.save(target / "ic_launcher.png")
        icon.save(target / "ic_launcher_round.png")

    foreground = Image.new("RGBA", (432, 432))
    place_mark(foreground, (70, 70, 362, 362))
    target = RES / "drawable-nodpi"
    target.mkdir(parents=True, exist_ok=True)
    foreground.save(target / "ic_launcher_foreground.png")


if __name__ == "__main__":
    main()
