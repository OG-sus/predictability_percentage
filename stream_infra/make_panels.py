"""
make_panels.py - Twitch panel header images in the Earth Watch stream's style.

    python stream_infra/make_panels.py

Writes 640x200 PNGs (Twitch shows panels 320 wide, so 2x stays sharp) to output/twitch_panels/.
Upload each one as the panel's image in Channel > About > Edit panels; panel text is in
CHANNEL_BRANDING.md.
"""
import io
import os
import sys

import requests
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from stream_renderer import BG_DARK, CYAN, FONT_PATH, LOGO_PATH, ImageFont  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "output", "twitch_panels")
W, H = 640, 200
GRAY = (150, 160, 175)
GREEN, AMBER, RED = (46, 204, 113), (255, 193, 77), (255, 77, 77)
GOES = "https://cdn.star.nesdis.noaa.gov/GOES19/ABI/FD/GEOCOLOR/1808x1808.jpg"

PANELS = [  # file, title, subtitle, accent
    ("01_watching", "WHAT AM I WATCHING?", "Earth, live from space, 24/7", CYAN),
    ("02_score", "WHAT DOES THE % MEAN?", "the FSR stability score", GREEN),
    ("03_cards", "THE LIVE CARDS", "storms . quakes . waves . water", CYAN),
    ("04_data", "WHERE THE DATA COMES FROM", "NOAA . NASA . USGS", CYAN),
    ("05_score_yours", "SCORE YOUR OWN DATA", "predictability-api.com", AMBER),
    ("06_youtube", "DAILY SHORTS", "StabilityNetwork on YouTube", RED),
    ("07_support", "SUPPORT THE STREAM", "keep Earth Watch live 24/7", GREEN),
    ("08_twitter", "FOLLOW ALONG", "updates & live events on X", CYAN),
]


def earth_disc(size):
    """Today's GOES-East globe as a round cutout, for the right edge of every panel."""
    try:
        img = Image.open(io.BytesIO(requests.get(GOES, timeout=60).content)).convert("RGB")
    except Exception:
        return None
    img = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([2, 2, size - 2, size - 2], fill=255)
    return img, mask.filter(ImageFilter.GaussianBlur(1))


def fit(draw, text, max_w, start):
    size = start
    while size > 16:
        font = ImageFont.truetype(FONT_PATH, size)
        if draw.textlength(text, font=font) <= max_w:
            return font
        size -= 2
    return ImageFont.truetype(FONT_PATH, size)


def main():
    os.makedirs(OUT, exist_ok=True)
    disc = earth_disc(260)
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((64, 64)) if os.path.exists(LOGO_PATH) else None
    for name, title, sub, accent in PANELS:
        img = Image.new("RGB", (W, H), BG_DARK)
        if disc:  # globe peeking in from the right, dimmed so text stays readable
            globe, mask = disc
            layer = Image.new("RGB", (W, H), BG_DARK)
            layer.paste(globe, (W - 170, (H - 260) // 2), mask)
            img = Image.blend(img, layer, 0.55)
        d = ImageDraw.Draw(img, "RGBA")
        d.rectangle([0, 0, 10, H], fill=accent)
        d.rectangle([0, H - 6, W, H], fill=(*CYAN, 255))
        x = 34
        if logo:
            img.paste(logo, (x, 30), logo)
            d.text((x + 80, 40), "FSR™ EARTH WATCH", font=ImageFont.truetype(FONT_PATH, 22), fill=GRAY)
        d.text((x, 104), title, font=fit(d, title, W - x - 200, 40), fill=CYAN)
        d.text((x, 152), sub, font=ImageFont.truetype(FONT_PATH, 22), fill=(220, 225, 232))
        path = os.path.join(OUT, name + ".png")
        img.save(path)
        print(path)


if __name__ == "__main__":
    main()
