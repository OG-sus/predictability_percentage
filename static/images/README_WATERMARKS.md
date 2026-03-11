Watermark assets

- `watermark_mono.svg` — single-color blue monogram (P%) for small icons.
- `watermark_mono_white.svg` — white monogram for dark video backgrounds.
- `watermark_lockup.svg` — compact icon + text lockup for branded watermark uses.
- Use `scripts/make_watermark.py` to generate PNG exports (128×128, 150×150, etc.).

Example command:

```
python scripts/make_watermark.py --input static/images/brand_logo.png --output static/images/watermark_128.png --size 128 --opacity 0.8
```
