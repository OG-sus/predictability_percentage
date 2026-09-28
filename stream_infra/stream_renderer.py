"""
stream_renderer.py - Volatility Radar frame renderer

Replaces the ticker.txt + ffmpeg drawtext(reload=1) approach entirely.
ffmpeg's docs warn that reload=1 "may fail" without perfectly atomic
file updates, and it reloads 30x/second - against a file rewritten
every few seconds that adds up to thousands of read attempts between
each actual update, and on Windows that occasionally collides with a
real (if rare) sharing violation that's fatal to ffmpeg. No shared
file, no race: this script renders each full frame itself and pipes
raw RGB24 frames straight into ffmpeg's stdin.

Visual language (colors, card style, FSR thresholds, scroller mechanics)
is lifted from the site's own existing assets rather than invented:
  templates/stream_ticker.html   - card grid, palette, FSR 80/60 tiers
  static/Obs/obs_ticker.html     - scroller mechanics, branded dividers

Run (feeds ffmpeg over a pipe, not directly watchable):
    python stream_renderer.py | ffmpeg -f rawvideo -pix_fmt rgb24 \
        -s 1280x720 -r 30 -i - ...

Reuses the data-fetching/scoring logic from ticker_feed_writer.py
(CoinGecko/Yahoo Finance/Open-Meteo/FRED) rather than duplicating it.
"""
import math
import os
import sys
import threading
import time
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ticker_feed_writer import build_assets, refresh_all  # noqa: E402

WIDTH, HEIGHT = 1280, 720
FRAME_SIZE = WIDTH * HEIGHT * 3  # rgb24, must match every frame exactly or ffmpeg's
                                  # rawvideo demuxer loses byte alignment for every
                                  # frame after a short one - this is what caused the
                                  # "Packet corrupt" error under memory pressure.
FPS = int(os.environ.get("STREAM_FPS", 20))  # run_stream.ps1 sets this so both sides always match
COLUMNS = 3
ROWS_PER_COL = 7
ROTATE_SECONDS = 20  # matches templates/stream_ticker.html's ROTATE_MS = 20000
REFRESH_INTERVAL = 120
MARQUEE_SPEED_PX_S = 90
MARQUEE_DIVIDER_EVERY = 8

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(HERE, "consola.ttf")
LOGO_PATH = os.path.join(HERE, "brand_logo.png")

# ---- Brand palette, lifted from templates/stream_ticker.html + obs_ticker.html ----
BG_DARK = (15, 17, 23)        # #0f1117
CYAN = (57, 194, 255)         # #39c2ff
AMBER = (255, 209, 102)       # #ffd166
GREEN = (0, 255, 136)         # #00ff88
RED = (255, 77, 77)           # #ff4d4d
GRAY = (170, 182, 196)        # #aab6c4
CARD_FILL = (255, 255, 255, 10)     # rgba(255,255,255,0.04)-ish
CARD_BORDER = (255, 255, 255, 18)   # rgba(255,255,255,0.07)-ish
MARQUEE_BG = (15, 17, 23, 235)


def score_color(score: float):
    # Same 80/60 tiers as templates/stream_ticker.html's fsrClass()
    if score >= 80:
        return GREEN
    if score >= 60:
        return AMBER
    return RED


def direction_color(direction: str):
    if direction == "up":
        return GREEN
    if direction == "down":
        return RED
    return GRAY


def direction_arrow(direction: str):
    return "^" if direction == "up" else "v" if direction == "down" else "-"


def build_background():
    """Near-flat dark background matching the site's #0f1117, with a
    very subtle diagonal shade for texture. Generated once."""
    top = (18, 20, 28)
    bottom = (11, 12, 18)
    img = Image.new("RGB", (WIDTH, HEIGHT))
    px = img.load()
    for y in range(HEIGHT):
        for x in range(0, WIDTH, 4):
            t = (x / WIDTH + y / HEIGHT) / 2
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            for dx in range(4):
                if x + dx < WIDTH:
                    px[x + dx, y] = (r, g, b)
    return img


def load_logo():
    if not os.path.exists(LOGO_PATH):
        return None
    logo = Image.open(LOGO_PATH).convert("RGBA")
    return logo.resize((44, 44))


class Renderer:
    def __init__(self):
        self.font_item = ImageFont.truetype(FONT_PATH, 19)
        self.font_score = ImageFont.truetype(FONT_PATH, 17)
        self.font_brand = ImageFont.truetype(FONT_PATH, 22)
        self.font_small = ImageFont.truetype(FONT_PATH, 14)
        self.font_marquee = ImageFont.truetype(FONT_PATH, 20)
        self.font_tagline = ImageFont.truetype(FONT_PATH, 15)
        self.font_category = ImageFont.truetype(FONT_PATH, 12)
        self.background = build_background()
        self.logo = load_logo()
        self.start_time = time.time()
        self._ribbon_cache = None
        self._ribbon_cache_at = 0.0
        # Only the clock, live dot, progress bar and marquee move frame to
        # frame - everything else is drawn once into _base and reused until
        # the grid's contents change (every rotation / data refresh). Redrawing
        # the whole frame 30x/s is what pegged the CPU on the laptop.
        self._base = None
        self._base_key = None
        self._ribbon_img = None
        self._ribbon_segments_drawn = None

    def draw_header_static(self, img, draw):
        draw.rectangle([0, 0, WIDTH, 88], fill=BG_DARK)
        draw.rectangle([0, 88, WIDTH, 90], fill=CYAN)

        x = 20
        if self.logo:
            img.paste(self.logo, (x, 12), self.logo)
            x += 54
        draw.text((x, 14), "FSR™ LIVE MARKETS", font=self.font_brand, fill=CYAN)
        draw.text((x, 46), "The FICO Score for Data Reliability   .   predictability-api.com",
                  font=self.font_tagline, fill=GRAY)

    def draw_header_live(self, draw):
        # Pulsing live dot (sine-wave alpha, same rhythm as the HTML's 2s CSS pulse)
        pulse = (math.sin((time.time() - self.start_time) * (2 * math.pi / 2.0)) + 1) / 2
        alpha = int(80 + 175 * pulse)
        dot_x = WIDTH - 150
        draw.ellipse([dot_x, 22, dot_x + 10, 32], fill=(*GREEN, alpha))

        clock = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        draw.text((dot_x + 20, 19), clock, font=self.font_small, fill=GRAY)

    def draw_progress_bar(self, draw, elapsed_in_cycle: float):
        frac = min(1.0, elapsed_in_cycle / ROTATE_SECONDS)
        draw.rectangle([0, 92, WIDTH, 96], fill=(*CYAN, 35))
        draw.rectangle([0, 92, int(WIDTH * frac), 96], fill=CYAN)

    def draw_grid(self, draw, batch):
        col_w, row_h, gap = 380, 64, 4
        for c in range(COLUMNS):
            x = 40 + c * (col_w + 40)
            col_batch = batch[c * ROWS_PER_COL:(c + 1) * ROWS_PER_COL]
            for i, asset in enumerate(col_batch):
                y = 104 + i * (row_h + gap)
                dcolor = direction_color(asset.direction)
                scolor = score_color(asset.last_score)

                draw.rounded_rectangle([x, y, x + col_w, y + row_h], radius=6, fill=CARD_FILL, outline=CARD_BORDER)
                draw.rectangle([x, y, x + 4, y + row_h], fill=dcolor)  # direction accent stripe

                draw.text((x + 16, y + 6), asset.display, font=self.font_item, fill=CYAN)
                score_text = f"{asset.last_score:.0f}%"
                score_w = draw.textlength(score_text, font=self.font_score)
                draw.text((x + col_w - 16 - score_w, y + 7), score_text, font=self.font_score, fill=scolor)

                price_text = f"{direction_arrow(asset.direction)}  {asset.last_price:,.2f}{asset.unit}"
                draw.text((x + 16, y + 28), price_text, font=self.font_small, fill=(230, 234, 240))

                draw.text((x + 16, y + 47), asset.category, font=self.font_category, fill=(120, 130, 145))

    def _ribbon_segments(self, all_assets):
        # Rebuilt at most once/second - text content barely changes faster
        # than that, and this avoids redoing string formatting every frame.
        now = time.time()
        if self._ribbon_cache and (now - self._ribbon_cache_at) < 1.0:
            return self._ribbon_cache

        segments = []
        dividers = [
            ("  ●  PREDICTABILITY-API.COM  ●  ", CYAN),
            ("  ●  SUBSCRIBE - STABILITYNETWORK ON YOUTUBE  ●  ", AMBER),
        ]
        shown = 0
        for a in all_assets:
            if a.last_score is None:
                continue
            text = f"{direction_arrow(a.direction)} {a.display} {a.last_score:.0f}%  {a.last_price:,.2f}{a.unit}"
            segments.append((text, score_color(a.last_score)))
            segments.append(("    ", GRAY))
            shown += 1
            if shown % MARQUEE_DIVIDER_EVERY == 0:
                segments.append(dividers[(shown // MARQUEE_DIVIDER_EVERY - 1) % len(dividers)])

        self._ribbon_cache = segments
        self._ribbon_cache_at = now
        return segments

    MARQUEE_TOP = HEIGHT - 56
    STRIP_TOP = MARQUEE_TOP + 2  # below the cyan rule

    def draw_marquee_static(self, draw):
        draw.rectangle([0, self.MARQUEE_TOP, WIDTH, HEIGHT], fill=MARQUEE_BG)
        draw.rectangle([0, self.MARQUEE_TOP, WIDTH, self.STRIP_TOP], fill=CYAN)

    def _build_ribbon(self, segments, strip_bg):
        """Pre-render the whole scrolling ribbon once, plus one screen-width of
        wrap-around, so each frame is just a crop instead of re-drawing ~200
        text segments."""
        measure = ImageDraw.Draw(self._base)
        widths = [measure.textlength(t, font=self.font_marquee) for t, _ in segments]
        ribbon_width = int(sum(widths))
        if ribbon_width <= 0:
            return None
        strip = Image.new("RGB", (ribbon_width + WIDTH, HEIGHT - self.STRIP_TOP), strip_bg)
        draw = ImageDraw.Draw(strip)
        cx = 0.0
        for (text, color), w in zip(segments, widths):
            draw.text((cx, 15), text, font=self.font_marquee, fill=color)
            cx += w
        # Copy the ribbon's start onto the end so the loop point is seamless.
        strip.paste(strip.crop((0, 0, WIDTH, strip.height)), (ribbon_width, 0))
        return strip, ribbon_width

    def draw_marquee_live(self, img, all_assets):
        segments = self._ribbon_segments(all_assets)
        if not segments:
            return
        if segments != self._ribbon_segments_drawn:
            strip_bg = self._base.getpixel((WIDTH // 2, HEIGHT - 5))
            self._ribbon_img = self._build_ribbon(segments, strip_bg)
            self._ribbon_segments_drawn = segments
        if not self._ribbon_img:
            return
        strip, ribbon_width = self._ribbon_img
        offset = int(((time.time() - self.start_time) * MARQUEE_SPEED_PX_S) % ribbon_width)
        img.paste(strip.crop((offset, 0, offset + WIDTH, strip.height)), (0, self.STRIP_TOP))

    def _base_frame(self, batch):
        key = tuple((a.display, a.last_score, a.last_price, a.direction) for a in batch)
        if key != self._base_key:
            img = self.background.copy()
            draw = ImageDraw.Draw(img, "RGBA")
            self.draw_header_static(img, draw)
            self.draw_grid(draw, batch)
            self.draw_marquee_static(draw)
            self._base, self._base_key = img, key
        return self._base

    def render(self, batch, all_assets, cycle_elapsed: float):
        img = self._base_frame(batch).copy()
        draw = ImageDraw.Draw(img, "RGBA")
        self.draw_header_live(draw)
        self.draw_progress_bar(draw, cycle_elapsed)
        self.draw_marquee_live(img, all_assets)
        return img


def write_full_frame(out, data: bytes) -> bool:
    """Write exactly one frame's worth of bytes, looping on short writes
    instead of trusting a single write() call to consume everything.
    Under system memory pressure a short write here would silently
    desync ffmpeg's rawvideo byte alignment for every subsequent frame,
    which is what produced the "Packet corrupt" error in practice.
    Returns False if the pipe closed (ffmpeg exited), so the caller can
    stop cleanly instead of ever sending a partial frame."""
    if len(data) != FRAME_SIZE:
        sys.stderr.write(f"stream_renderer: frame size mismatch ({len(data)} != {FRAME_SIZE}), skipping\n")
        return True
    view = memoryview(data)
    written = 0
    while written < len(view):
        n = out.write(view[written:])
        if not n:
            return False
        written += n
    return True


def rotation_loop(all_assets, columns, rows_per_col, rotate_seconds, state, stop_event):
    batch_size = columns * rows_per_col
    cursor = 0
    while not stop_event.is_set():
        ready = [a for a in all_assets if a.last_score is not None]
        if ready:
            n = min(batch_size, len(ready))
            batch = [ready[(cursor + i) % len(ready)] for i in range(n)]
            cursor = (cursor + n) % len(ready)
            state["batch"] = batch
            state["cycle_start"] = time.time()
        stop_event.wait(rotate_seconds)


def main():
    groups, all_assets = build_assets()

    stop_event = threading.Event()

    def refresh_loop():
        while not stop_event.is_set():
            refresh_all(groups)
            stop_event.wait(REFRESH_INTERVAL)

    threading.Thread(target=refresh_loop, daemon=True).start()

    state = {"batch": [], "cycle_start": time.time()}
    threading.Thread(
        target=rotation_loop,
        args=(all_assets, COLUMNS, ROWS_PER_COL, ROTATE_SECONDS, state, stop_event),
        daemon=True,
    ).start()

    sys.stderr.write("stream_renderer: waiting for first data snapshot...\n")
    sys.stderr.flush()
    time.sleep(8)

    renderer = Renderer()
    out = sys.stdout.buffer

    frame_interval = 1.0 / FPS
    next_frame_at = time.time()
    try:
        while True:
            cycle_elapsed = time.time() - state["cycle_start"]
            img = renderer.render(state["batch"], all_assets, cycle_elapsed)
            if not write_full_frame(out, img.tobytes()):
                break

            next_frame_at += frame_interval
            sleep_for = next_frame_at - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
            elif sleep_for < -1.0:
                # Way behind (machine asleep, long stall) - resync instead of spiraling.
                next_frame_at = time.time()
            # A short hiccup (a data refresh holding the GIL, etc.) is caught up by
            # sending the next few frames back to back. Resyncing on every small
            # stall used to throw that time away, which is why ffmpeg sat at
            # ~0.98x instead of 1.0x. Frames only take ~4ms, so catching up is cheap.
    except (OSError, KeyboardInterrupt):
        # OSError covers BrokenPipeError plus the EINVAL Windows raises when
        # ffmpeg has exited (e.g. the RTMP connection dropped).
        pass
    finally:
        stop_event.set()
        # Exit hard: the data-refresh thread can be stuck in a 20s network
        # timeout, and a lingering renderer is what kept logging after the
        # stream died instead of letting run_stream.ps1 restart cleanly.
        os._exit(0)


if __name__ == "__main__":
    main()
