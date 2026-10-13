"""
earth_watch.py - live "from space" data for the stream's Earth Watch view

Everything here is public-domain US government data, safe to show on a 24/7 stream:
  - GOES-19 (East) / GOES-18 (West) full-disk GeoColor Earth images, new every 10 minutes (NOAA)
  - NASA Worldview close-ups of whatever is happening (active hurricane, big earthquake)
  - Sensor cards, each scored live by the FSR engine:
        hurricanes (NHC 6-hourly track), world earthquakes (USGS, daily counts),
        a Gulf ocean buoy's wave height (NOAA NDBC, hourly), groundwater (NASA, saved file)

EarthWatch.refresh() does all the network work and is meant to run on a background thread;
the renderer only ever reads EarthWatch.snapshot(), so a slow or failed fetch never stalls frames.
Every source is optional - if one fails, its card just keeps its last good value.
"""
import io
import math
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fsr import calculate_predictability  # noqa: E402

UA = {"User-Agent": "predictability-api.com Earth Watch stream"}
GOES = {
    "GOES-19 (East)": "https://cdn.star.nesdis.noaa.gov/GOES19/ABI/FD/GEOCOLOR/1808x1808.jpg",
    "GOES-18 (West)": "https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/GEOCOLOR/1808x1808.jpg",
}
WORLDVIEW = "https://wvs.earthdata.nasa.gov/api/v1/snapshot"
NHC_CURRENT = "https://www.nhc.noaa.gov/CurrentStorms.json"
NHC_BTK = "https://ftp.nhc.noaa.gov/atcf/btk/b{id}.dat"
USGS_MONTH = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_month.geojson"
NDBC_LATEST = "https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt"   # every buoy's newest reading
NDBC_STATIONS = "https://www.ndbc.noaa.gov/activestations.xml"            # buoy names
NDBC_SERIES = "https://www.ndbc.noaa.gov/data/realtime2/{st}.txt"         # one buoy's last 45 days
FALLBACK_BUOY = "42001"  # Mid-Gulf, used only if the all-buoys feed is down

# Groundwater regions the water card rotates through (made by groundwater_gen.py --preset <name>).
# A region whose file doesn't exist yet is just skipped; files older than a month are re-pulled
# from NASA in the background (needs EARTHDATA_TOKEN in .env).
WATER_REGIONS = {
    "texas_panhandle": "TEXAS PANHANDLE",
    "high_plains": "HIGH PLAINS, KANSAS",
    "central_valley": "CENTRAL VALLEY, CALIF.",
    "southwest": "MESILLA BASIN, N.M.",
    "phoenix": "PHOENIX, ARIZONA",
}
WATER_STALE_DAYS = 32

FOCUS_STORM_KT = 64      # hurricanes (64 kt+) take over the main image
FOCUS_QUAKE_MAG = 6.5    # so do M6.5+ quakes in the last 24 hours

TOP_STORMS = 3           # storm card rotates through up to this many active storms, strongest first
TOP_BUOYS = 5            # buoy card rotates through the buoys with the biggest waves right now
ROTATE_SECONDS = 60      # each rotating card shows one item this long (cards are staggered 20s apart)
STORM_BUOY_KM = 800      # a buoy this close to a hurricane jumps to the front of the buoy rotation


def _get(url, **kw):
    r = requests.get(url, headers=UA, timeout=kw.pop("timeout", 30), **kw)
    r.raise_for_status()
    return r


def fsr(values, window, k=1.0):
    """Latest sliding-window FSR, or None if there isn't enough data."""
    if len(values) < window:
        return None
    return calculate_predictability(values[-window:], k)


def saffir(kt):
    for cat, lo in ((5, 137), (4, 113), (3, 96), (2, 83), (1, 64)):
        if kt >= lo:
            return f"Cat {cat}"
    return "Tropical storm" if kt >= 34 else "Depression"


def _km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def _missing_fraction(img):
    """Share of pixels that are pure black = no satellite data there (real night/ocean is never 0,0,0
    in GeoColor; coastline lines are drawn over gaps, so allow a little brightness)."""
    small = img.resize((140, 140)).convert("L")
    return sum(1 for p in small.getdata() if p < 6) / (140 * 140)


def _wave_series(station, hours=72):
    """Hourly wave height (m) for one NDBC station, oldest first (first reading of each hour)."""
    lines = _get(NDBC_SERIES.format(st=station)).text.splitlines()
    hdr = lines[0].lstrip("#").split()
    i = hdr.index("WVHT")
    seen, v = set(), []
    for row in reversed([ln.split() for ln in lines[2:]]):
        if len(row) > i and row[i] != "MM" and tuple(row[:4]) not in seen:
            seen.add(tuple(row[:4]))
            v.append(float(row[i]))
    return v[-hours:]


def _short_name(name, station):
    """'Station 46006 - SE Papa - 600NM West of Eureka, CA' -> 'SE PAPA'"""
    parts = [x.strip() for x in name.split(" - ") if x.strip() and not x.strip().lower().startswith("station")]
    name = re.sub(r"\s*\(.*$", "", parts[0]) if parts else f"BUOY {station}"  # drop "(256)"-style suffixes
    name = re.sub(r"\s+AWS$", "", name)  # AWS = offshore weather station
    return name.upper()[:34]


class EarthWatch:
    def __init__(self, image_size=560):
        self.size = image_size
        self._lock = threading.Lock()
        # "sets" holds a list of cards per slot; snapshot() picks which one is showing right now.
        self._state = {"image": None, "caption": "Loading satellite view...", "focus": None,
                       "sets": {}, "version": 0}
        self._goes_turn = 0
        self._buoy_names = None
        self._water_job = None

    # ---- public -----------------------------------------------------------------------
    def snapshot(self):
        with self._lock:
            state = dict(self._state)
        cards, ticks = {}, []
        for n, (slot, items) in enumerate(sorted(state.pop("sets").items())):
            if not items:
                continue
            tick = int((time.time() + n * 20) // ROTATE_SECONDS)  # stagger so cards don't all flip at once
            card = dict(items[tick % len(items)])
            if len(items) > 1:
                card["note"] = f"{tick % len(items) + 1}/{len(items)}  .  " + card.get("note", "")
            cards[slot] = card
            ticks.append(tick % len(items))
        state["cards"] = cards
        state["version"] = (state["version"], tuple(ticks))  # renderer redraws when either changes
        return state

    def refresh(self):
        storms, quake = self._safe(self._storms), self._safe(self._quakes)
        with self._lock:
            sets = dict(self._state["sets"])
        if storms is not None:
            sets["storm"] = storms["cards"]
        if quake is not None:
            sets["quakes"] = [quake["card"]]
        buoys = self._safe(lambda: self._buoys(storms.get("focus") if storms else None))
        if buoys:
            sets["buoy"] = buoys
        water = self._safe(self._waters)
        if water:
            sets["water"] = water

        # Hurricane first, then a big quake; if one's close-up has no imagery, try the next.
        focus, image, caption = None, None, None
        for f in [x.get("focus") for x in (storms, quake) if x and x.get("focus")]:
            image, caption = self._safe(lambda: self._closeup(f)) or (None, None)
            if image is not None:
                focus = f
                break
        if image is None:
            image, caption = self._safe(self._full_disk) or (None, None)

        with self._lock:
            if image is not None:
                self._state["image"], self._state["caption"] = image, caption
            self._state["focus"] = focus
            self._state["sets"] = sets
            self._state["version"] += 1

    # ---- images -----------------------------------------------------------------------
    def _full_disk(self):
        name = list(GOES)[self._goes_turn % len(GOES)]
        self._goes_turn += 1
        img = Image.open(io.BytesIO(_get(GOES[name], timeout=60).content)).convert("RGB")
        img = img.resize((self.size, self.size), Image.LANCZOS)
        return img, f"LIVE FROM SPACE  .  {name}  .  NOAA  .  {datetime.now(timezone.utc):%H:%M} UTC"

    def _closeup(self, focus):
        """Worldview satellite close-up centered on the event, with a marker on it."""
        lat, lon = focus["lat"], focus["lon"]
        half = 8.0
        bbox = f"{lat - half},{lon - half},{lat + half},{lon + half}"
        now = datetime.now(timezone.utc)
        if -150 <= lon <= -20:  # GOES geostationary coverage: near-real-time, every 10 min
            layer = "GOES-East_ABI_GeoColor" if lon > -105 else "GOES-West_ABI_GeoColor"
            source = "GOES-East" if lon > -105 else "GOES-West"
            # Worldview's GOES tiles lag by a variable amount (GOES-West was 40-70 min behind on
            # Oct 13 2026), so step back until a frame has actual imagery in it.
            tries = []
            for mins in (40, 70, 100, 130, 180, 240):
                t = now - timedelta(minutes=mins)
                tries.append(t.replace(minute=t.minute // 10 * 10, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"))
        else:  # elsewhere: polar-orbit true color, yesterday's (or the day before's) pass
            layer = "VIIRS_SNPP_CorrectedReflectance_TrueColor"
            source = "NASA VIIRS"
            tries = [(now - timedelta(days=d)).strftime("%Y-%m-%d") for d in (1, 2)]
        r = None
        for when in tries:
            r = _get(WORLDVIEW, timeout=60, params={
                "REQUEST": "GetSnapshot", "TIME": when, "BBOX": bbox, "CRS": "EPSG:4326",
                "LAYERS": f"{layer},Coastlines_15m", "FORMAT": "image/jpeg", "WIDTH": self.size, "HEIGHT": self.size})
            if len(r.content) < 20000:  # under ~20 KB = mostly-empty tile, no imagery yet
                continue
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            if _missing_fraction(img) <= 0.05:  # partly-filled tiles have big pure-black gaps
                break
        else:
            return None
        d = ImageDraw.Draw(img)
        c = self.size // 2
        d.ellipse([c - 14, c - 14, c + 14, c + 14], outline=(255, 77, 77), width=3)
        stamp = when[11:16] + " UTC" if "T" in when else when  # how old the picture is
        return img, f"FROM SPACE  .  {focus['label']}  .  {source}  .  {stamp}"

    # ---- sensor cards -----------------------------------------------------------------
    def _storms(self):
        active = _get(NHC_CURRENT).json().get("activeStorms", [])
        if not active:
            return {"cards": [{"title": "TROPICS", "value": "No active storms", "score": None, "series": [],
                               "note": "NOAA National Hurricane Center"}], "focus": None}
        active = sorted(active, key=lambda x: int(x.get("intensity") or 0), reverse=True)
        cards = []
        for s in active[:TOP_STORMS]:
            kt = int(s["intensity"])
            winds = []
            try:
                pts = {}
                for line in _get(NHC_BTK.format(id=s["id"])).text.splitlines():
                    f = [x.strip() for x in line.split(",")]
                    if len(f) > 8 and f[8]:
                        pts[f[2]] = int(f[8])
                winds = [pts[t] for t in sorted(pts)]
            except Exception:
                pass
            cards.append({"title": f"HURRICANE WATCH  .  {s['name'].upper()}" if kt >= 64 else f"TROPICS  .  {s['name'].upper()}",
                          "value": f"{saffir(kt)}  {kt} kt / {round(kt * 1.15078)} mph  .  {s['pressure']} mb",
                          "score": fsr(winds, 4), "series": winds[-40:],
                          "note": f"{len(active)} active storm{'s' if len(active) != 1 else ''}  .  24h stability"})
        s, focus = active[0], None
        if int(s["intensity"]) >= FOCUS_STORM_KT:
            focus = {"lat": float(s["latitudeNumeric"]), "lon": float(s["longitudeNumeric"]),
                     "label": f"Hurricane {s['name']}, {saffir(int(s['intensity']))}"}
        return {"cards": cards, "focus": focus}

    def _quakes(self):
        feats = _get(USGS_MONTH, timeout=60).json()["features"]
        now = time.time() * 1000
        days = {}
        for q in feats:
            day = datetime.fromtimestamp(q["properties"]["time"] / 1000, timezone.utc).date()
            days[day] = days.get(day, 0) + 1
        today = datetime.now(timezone.utc).date()
        series = [days.get(today - timedelta(days=i), 0) for i in range(29, -1, -1)]
        last24 = [q for q in feats if now - q["properties"]["time"] < 86400000]
        big = max(last24, key=lambda q: q["properties"]["mag"] or 0) if last24 else None
        value = f"{len(last24)} quakes M4.5+ in 24h"
        if big:
            value += f"  .  biggest M{big['properties']['mag']:.1f}"
        card = {"title": "EARTHQUAKES  .  WORLDWIDE", "value": value, "score": fsr(series[:-1], 7),
                "series": series[:-1], "note": (big["properties"]["place"][:44] if big else "USGS") + "  .  7-day stability"}
        focus = None
        if big and (big["properties"]["mag"] or 0) >= FOCUS_QUAKE_MAG:
            lon, lat = big["geometry"]["coordinates"][:2]
            focus = {"lat": lat, "lon": lon, "label": f"M{big['properties']['mag']:.1f} earthquake"}
        return {"card": card, "focus": focus}

    def _buoys(self, storm_focus=None):
        """The buoys with the biggest waves right now (any in NOAA's network), biggest first.
        During a hurricane, the reporting buoy nearest the storm goes to the front."""
        if self._buoy_names is None:
            try:
                xml = _get(NDBC_STATIONS).text
                self._buoy_names = {m.group(1): m.group(2) for m in
                                    re.finditer(r'<station id="(\w+)"[^>]*?name="([^"]*)"', xml)}
            except Exception:
                self._buoy_names = {}
        latest = []
        for ln in _get(NDBC_LATEST).text.splitlines()[2:]:
            f = ln.split()
            if len(f) > 11 and f[11] != "MM":
                latest.append((f[0], float(f[1]), float(f[2]), float(f[11])))
        ranked = sorted(latest, key=lambda b: -b[3])
        storm_st = None
        if storm_focus and latest:
            near = min(latest, key=lambda b: _km(b[1], b[2], storm_focus["lat"], storm_focus["lon"]))
            if _km(near[1], near[2], storm_focus["lat"], storm_focus["lon"]) <= STORM_BUOY_KM:
                storm_st = near[0]
                ranked = [near] + [b for b in ranked if b[0] != near[0]]
        where = {b[0]: f"{abs(b[1]):.0f}°{'N' if b[1] >= 0 else 'S'} {abs(b[2]):.0f}°{'E' if b[2] >= 0 else 'W'}"
                 for b in ranked}
        picks = [b[0] for b in ranked] or [FALLBACK_BUOY]
        cards = []
        for st in picks:
            if len(cards) >= TOP_BUOYS:
                break
            try:
                v = _wave_series(st)
            except Exception:
                continue  # some stations in the feed have no realtime2 file
            if len(v) < 24:
                continue
            name = _short_name(self._buoy_names.get(st, ""), st)
            cards.append({"title": f"OCEAN  .  {name}"[:46],
                          "value": f"Waves {v[-1]:.1f} m  ({v[-1] * 3.281:.0f} ft)",
                          "score": fsr(v, 24), "series": v,
                          "note": ("nearest buoy to the hurricane" if st == storm_st else "biggest waves now")
                                  + f"  .  {where.get(st, 'NOAA ' + st)}  .  24h stability"})
        return cards

    def _waters(self):
        cards = []
        for slug, label in WATER_REGIONS.items():
            path = os.path.join(ROOT, "output", f"groundwater_{slug}.txt")
            self._maybe_refresh_water(slug, path)
            if not os.path.exists(path):
                continue
            v = [float(x) for x in open(path).read().split(",") if x.strip()]
            if len(v) < 12:
                continue
            years = round(len(v) / 12)
            low = v[-1] <= min(v) * 1.005
            cards.append({"title": f"WATER  .  {label}", "value": f"Groundwater {v[-1]:.0f} mm"
                          + (f"  .  {years}-yr low" if low else ""), "score": fsr(v, 6), "series": v,
                          "note": "NASA, measured from space  .  6-mo stability"})
        return cards

    def _maybe_refresh_water(self, slug, path):
        """Re-pull a region from NASA in the background when its file is missing or a month old.
        One at a time, so the stream never runs several downloads at once."""
        if self._water_job is not None and self._water_job.poll() is None:
            return
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < WATER_STALE_DAYS * 86400:
            return
        try:
            self._water_job = subprocess.Popen(
                [sys.executable, os.path.join(ROOT, "groundwater_gen.py"), "--preset", slug],
                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sys.stderr.write(f"earth_watch: refreshing groundwater for {slug} in the background\n")
        except Exception as e:
            sys.stderr.write(f"earth_watch: couldn't start groundwater refresh: {e}\n")

    @staticmethod
    def _safe(fn):
        try:
            return fn()
        except Exception as e:
            sys.stderr.write(f"earth_watch: {getattr(fn, '__name__', 'fetch')} failed: {type(e).__name__}: {e}\n")
            return None


def refresh_loop(ew, stop_event, interval=600):
    while not stop_event.is_set():
        ew.refresh()
        stop_event.wait(interval)
