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
import traceback
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
MARQUEE_PX_PER_FRAME = 4  # whole pixels per frame = perfectly even steps (4 px x 20 fps = 80 px/s)
MARQUEE_DIVIDER_EVERY = 8

HERE = os.path.dirname(os.path.abspath(__file__))
# Consolas is a Windows font (gitignored, can't ship it), so on the Linux VPS fall back to
# DejaVu Sans Mono (apt install fonts-dejavu-core), which has nearly the same metrics.
FONT_PATH = next((p for p in (os.path.join(HERE, "consola.ttf"),
                              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
                  if os.path.exists(p)), os.path.join(HERE, "consola.ttf"))
LOGO_PATH = next((p for p in (os.path.join(HERE, "brand_logo.png"),
                              os.path.join(os.path.dirname(HERE), "static", "images", "brand_logo.png"))
                  if os.path.exists(p)), os.path.join(HERE, "brand_logo.png"))

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
        self.frame_no = 0  # frames sent to ffmpeg so far (set by main); the ticker moves by this, not the clock
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
        # By frame count, not wall clock: ffmpeg plays frame N at N/FPS, so clock-based offsets
        # jittered by however early/late each frame happened to be drawn.
        offset = (self.frame_no * MARQUEE_PX_PER_FRAME) % ribbon_width
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

    # ---- Earth Watch layout: live satellite image + FSR sensor cards, ticker along the bottom ----
    EW_IMG = 556
    CARD_ORDER = ("storm", "quakes", "buoy", "water")

    def draw_earth_header(self, img, draw, focus):
        draw.rectangle([0, 0, WIDTH, 88], fill=BG_DARK)
        draw.rectangle([0, 88, WIDTH, 90], fill=RED if focus else CYAN)
        x = 20
        if self.logo:
            img.paste(self.logo, (x, 12), self.logo)
            x += 54
        draw.text((x, 14), "FSR™ EARTH WATCH", font=self.font_brand, fill=CYAN)
        draw.text((x, 46), "Live from space, scored by the stability engine   .   predictability-api.com",
                  font=self.font_tagline, fill=GRAY)

    def draw_sparkline(self, draw, box, series, color):
        x0, y0, x1, y1 = box
        if len(series) < 2:
            return
        lo, hi = min(series), max(series)
        span = (hi - lo) or 1.0
        pts = [(x0 + (x1 - x0) * i / (len(series) - 1), y1 - (y1 - y0) * (v - lo) / span)
               for i, v in enumerate(series)]
        draw.line(pts, fill=(*color, 230), width=2)
        draw.ellipse([pts[-1][0] - 3, pts[-1][1] - 3, pts[-1][0] + 3, pts[-1][1] + 3], fill=color)

    def draw_earth_card(self, draw, x, y, w, h, card):
        draw.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=CARD_FILL, outline=CARD_BORDER)
        score = card.get("score")
        scolor = score_color(score) if score is not None else GRAY
        draw.rectangle([x, y, x + 4, y + h], fill=scolor)
        draw.text((x + 16, y + 10), card["title"][:46], font=self.font_category, fill=CYAN)
        draw.text((x + 16, y + 30), card["value"][:44], font=self.font_item, fill=(235, 238, 244))
        draw.text((x + 16, y + h - 24), card.get("note", "")[:58], font=self.font_category, fill=(120, 130, 145))
        if score is not None:
            txt = f"{score:.0f}%"
            draw.text((x + w - 16 - draw.textlength(txt, font=self.font_brand), y + 8), txt,
                      font=self.font_brand, fill=scolor)
            draw.text((x + w - 16 - draw.textlength("FSR", font=self.font_category), y + 36), "FSR",
                      font=self.font_category, fill=GRAY)
        self.draw_sparkline(draw, (x + 16, y + 60, x + w - 16, y + h - 30), card.get("series", []), scolor)

    LOOP_FRAME_S = 0.5   # close-up loop: each satellite frame shows this long...
    LOOP_HOLD_S = 2.5    # ...and the newest one holds a bit, so the loop reads as "now"

    def _loop_index(self, n):
        if n <= 1:
            return 0
        t = time.time() % ((n - 1) * self.LOOP_FRAME_S + self.LOOP_HOLD_S)
        return min(int(t // self.LOOP_FRAME_S), n - 1)

    def _earth_base(self, ew):
        frames = ew.get("image") or []
        if not isinstance(frames, list):
            frames = [frames]
        idx = self._loop_index(len(frames))
        key = (ew["version"], idx)
        if key == self._base_key:
            return self._base
        # One finished base per loop frame, kept until the data changes, so animating is a dict lookup.
        cache = getattr(self, "_earth_cache", None)
        if cache is None or cache.get("_v") != ew["version"]:
            cache = self._earth_cache = {"_v": ew["version"]}
        if idx in cache:
            self._base, self._base_key = cache[idx], key
            return self._base
        img = self.background.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        self.draw_earth_header(img, draw, ew.get("focus"))
        ix, iy = 22, 100
        if frames:
            img.paste(frames[idx].resize((self.EW_IMG, self.EW_IMG)), (ix, iy))
        else:
            draw.rectangle([ix, iy, ix + self.EW_IMG, iy + self.EW_IMG], fill=(8, 10, 16))
        draw.rectangle([ix, iy + self.EW_IMG - 26, ix + self.EW_IMG, iy + self.EW_IMG], fill=(10, 12, 18, 200))
        draw.text((ix + 10, iy + self.EW_IMG - 21), ew.get("caption", "")[:70], font=self.font_category, fill=GRAY)
        if ew.get("focus"):
            draw.rounded_rectangle([ix + 10, iy + 10, ix + 160, iy + 36], radius=6, fill=(*RED, 220))
            draw.text((ix + 20, iy + 14), "LIVE EVENT", font=self.font_score, fill=(255, 255, 255))
        cards = [ew["cards"][k] for k in self.CARD_ORDER if k in ew.get("cards", {})]
        cx, cw, top, bottom = ix + self.EW_IMG + 22, WIDTH - (ix + self.EW_IMG + 22) - 22, 100, self.MARQUEE_TOP - 8
        if cards:
            gap = 8
            ch = (bottom - top - gap * (len(cards) - 1)) // len(cards)
            for n, card in enumerate(cards):
                self.draw_earth_card(draw, cx, top + n * (ch + gap), cw, ch, card)
        self.draw_marquee_static(draw)
        cache[idx] = img
        self._base, self._base_key = img, key
        return img

    def render_earth(self, ew, all_assets):
        img = self._earth_base(ew).copy()
        draw = ImageDraw.Draw(img, "RGBA")
        self.draw_header_live(draw)
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


LAYOUT = os.environ.get("STREAM_LAYOUT", "earth")  # "earth" (Earth Watch, default) or "markets" (old grid)


def main():
    groups, all_assets = build_assets()

    stop_event = threading.Event()
    earth = None
    if LAYOUT == "earth":
        from earth_watch import EarthWatch, refresh_loop as earth_loop
        earth = EarthWatch()
        threading.Thread(target=earth_loop, args=(earth, stop_event), daemon=True).start()

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
    last_frame, render_errors = None, 0
    try:
        while True:
            # A drawing bug (odd data in a card, etc.) must never kill the stream: log it and
            # resend the last good frame. Without this, the exception went straight to the
            # os._exit below (no traceback printed) and ffmpeg kept streaming music over nothing.
            try:
                if earth is not None:
                    img = renderer.render_earth(earth.snapshot(), all_assets)
                else:
                    cycle_elapsed = time.time() - state["cycle_start"]
                    img = renderer.render(state["batch"], all_assets, cycle_elapsed)
                last_frame = img.tobytes()
            except Exception:
                render_errors += 1
                if render_errors <= 3 or render_errors % 1000 == 0:
                    sys.stderr.write(f"stream_renderer: frame error #{render_errors}\n{traceback.format_exc()}")
                    sys.stderr.flush()
                if last_frame is None:
                    raise
            renderer.frame_no += 1
            if not write_full_frame(out, last_frame):
                sys.stderr.write("stream_renderer: output pipe closed (write returned 0), exiting\n")
                break

            next_frame_at += frame_interval
            sleep_for = next_frame_at - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
            elif sleep_for < -frame_interval:
                # Behind (busy laptop, a data refresh, the stream deprioritized). ffmpeg times
                # video by frame COUNT, so every frame we skip is lost time: it's what pushed
                # speed to ~0.9x and made viewers buffer. Fill the gap by resending the last
                # frame (a ~1 ms pipe write vs ~9 ms to draw one) so output stays real-time;
                # viewers see a brief freeze instead of a buffering wheel.
                missed = int(-sleep_for / frame_interval)
                if missed > FPS * 10:  # machine slept / suspended - resync, don't flood ffmpeg
                    next_frame_at = time.time()
                else:
                    for _ in range(missed):
                        renderer.frame_no += 1
                        if not write_full_frame(out, last_frame):
                            break
                    next_frame_at += missed * frame_interval
    except (OSError, KeyboardInterrupt) as e:
        # OSError covers BrokenPipeError plus the EINVAL Windows raises when
        # ffmpeg has exited (e.g. the RTMP connection dropped).
        sys.stderr.write(f"stream_renderer: exiting on {type(e).__name__}: {e}\n")
        sys.stderr.flush()
    except Exception:
        sys.stderr.write(f"stream_renderer: fatal error\n{traceback.format_exc()}")
        sys.stderr.flush()
    finally:
        stop_event.set()
        # Exit hard: the data-refresh thread can be stuck in a 20s network
        # timeout, and a lingering renderer is what kept logging after the
        # stream died instead of letting run_stream.ps1 restart cleanly.
        os._exit(0)


if __name__ == "__main__":
    main()
