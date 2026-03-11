from PIL import Image, ImageOps

def make_watermark(input_path, output_path, size=128, opacity=0.8, padding_frac=0.12):
    src = Image.open(input_path).convert("RGBA")
    pad = int(size * padding_frac)
    content_size = size - pad * 2
    src.thumbnail((content_size, content_size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - src.width) // 2
    y = (size - src.height) // 2
    canvas.paste(src, (x, y), src)
    if opacity < 1.0:
        alpha = canvas.split()[3]
        alpha = Image.eval(alpha, lambda a: int(a * opacity))
        canvas.putalpha(alpha)
    canvas.save(output_path, format="PNG")
    print(f"Saved {output_path}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Input image path (PNG/SVG via pillow-SVG plugin optional)")
    p.add_argument("--output", required=True)
    p.add_argument("--size", type=int, default=128)
    p.add_argument("--opacity", type=float, default=0.8)
    args = p.parse_args()
    make_watermark(args.input, args.output, size=args.size, opacity=args.opacity)
