from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = "static/images"
os.makedirs(OUT_DIR, exist_ok=True)

def load_font(size):
    try:
        # Try Segoe UI or Arial if available
        return ImageFont.truetype("Segoe UI.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

def make_monogram(color, out_path, size=128, padding=0.12):
    canvas = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(canvas)
    # draw large text
    font_size = int(size * 0.7)
    font = load_font(font_size)
    text = "P%"
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except Exception:
        w, h = font.getsize(text)
    draw.text(((size-w)/2, (size-h)/2 - size*0.03), text, font=font, fill=color)
    canvas.save(out_path)
    print(f"Saved {out_path}")

def make_lockup(out_path, size=128):
    canvas = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(canvas)
    # circle icon
    cx = int(size * 0.22)
    cy = size//2
    r = int(size * 0.18)
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill="#0170C1")
    # P% inside circle
    font = load_font(int(r*1.4))
    text = "P%"
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except Exception:
        w, h = font.getsize(text)
    draw.text((cx - w/2, cy - h/2 - size*0.02), text, font=font, fill="#ffffff")
    # text lockup
    font_title = load_font(int(size*0.14))
    font_sub = load_font(int(size*0.09))
    draw.text((int(size*0.45), int(size*0.34)), "Predictability", font=font_title, fill="#222222")
    draw.text((int(size*0.45), int(size*0.58)), "Score", font=font_sub, fill="#555555")
    canvas.save(out_path)
    print(f"Saved {out_path}")

def make_universal(out_path, size=128, stroke_width=2):
    canvas = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(canvas)
    font = load_font(int(size * 0.7))
    text = "P%"
    try:
        bbox = draw.textbbox((0,0), text, font=font, stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except Exception:
        w, h = font.getsize(text)
    x = (size - w) / 2
    y = (size - h) / 2 - size * 0.03
    # Draw white fill with dark stroke for universal readability
    draw.text((x, y), text, font=font, fill="#FFFFFF", stroke_width=stroke_width, stroke_fill="#222222")
    canvas.save(out_path)
    print(f"Saved {out_path}")

if __name__ == '__main__':
    make_monogram("#0170C1", os.path.join(OUT_DIR, "watermark_mono_128.png"), size=128)
    make_monogram("#FFFFFF", os.path.join(OUT_DIR, "watermark_mono_white_128.png"), size=128)
    make_lockup(os.path.join(OUT_DIR, "watermark_lockup_128.png"), size=128)
    make_universal(os.path.join(OUT_DIR, "watermark_universal_128.png"), size=128, stroke_width=2)
