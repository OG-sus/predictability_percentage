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
GOES_SUBLON = {"GOES-19 (East)": -75.2, "GOES-18 (West)": -137.0}  # where each satellite parks over the equator
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

# Worldwide fire card (NASA FIRMS, needs FIRMS_MAP_KEY in .env). Daily counts are cached so a refresh
# only downloads days it hasn't seen; one world-day is ~0.5 MB and ~35 of the key's 5,000 calls / 10 min.
FIRMS_AREA = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/MODIS_NRT/world/1/{day}"
FIRE_CACHE = os.path.join(ROOT, "output", "firms_cache", "world_daily.json")
FIRE_DAYS = 30
FIRE_REGIONS = (  # rough boxes, only for naming the busiest region on the card
    ("South America", -35, 6, -82, -34), ("Central Africa", -20, 15, 5, 50), ("Indonesia", -12, 8, 94, 141),
    ("Australia", -45, -10, 110, 155), ("India", 5, 30, 65, 100), ("USA", 24, 50, -125, -66),
    ("Canada", 49, 72, -141, -52), ("Siberia", 50, 75, 60, 180), ("Mexico", 14, 33, -118, -86),
    ("Southeast Asia", 8, 28, 92, 110), ("Europe", 35, 70, -10, 45),
)

# Space weather, sea ice and world temperature cards (all free, no key)
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"          # 3-hourly, last ~7 days
SOLAR_WIND_URL = "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"             # 1-minute, ~1 week
SEA_ICE_URL = "https://noaadata.apps.nsidc.org/NOAA/G02135/north/daily/data/N_seaice_extent_daily_v4.0.csv"
WORLD_TEMP_URL = "https://climatereanalyzer.org/clim/t2_daily/json/era5_world_t2_day.json"  # ERA5, daily since 1940

CARD_COLORS = {  # title + line color per card type (RGB)
    "storm": (255, 120, 90), "quakes": (190, 150, 255), "aurora": (90, 235, 160), "solar": (255, 220, 90),
    "ocean": (80, 175, 255), "ice": (190, 230, 255), "fire": (255, 140, 40), "temp": (255, 105, 140),
    "water": (60, 140, 255),
}

FOCUS_STORM_KT = 64      # hurricanes (64 kt+) take over the main image
FOCUS_QUAKE_MAG = 6.5    # so do M6.5+ quakes in the last 24 hours

TOP_STORMS = 3           # storm card rotates through up to this many active storms, strongest first
TOP_BUOYS = 5            # buoy card rotates through the buoys with the biggest waves right now
ROTATE_SECONDS = 45      # each rotating card shows one item this long (cards are staggered 15s apart)
EVENT_CYCLE_SECONDS = 180  # during a live event: the close-up loop for 90 s...
GLOBE_SECONDS = 90         # ...then the whole globe for 90 s, repeating
LOOP_FRAMES = 8          # close-up loop length: 8 frames x 10 min = the last ~80 minutes
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


def _geo_xy(lat, lon, sub_lon):
    """Where a lat/lon lands on a GOES full-disk image, as 0-1 fractions across and down
    (GOES-R fixed-grid projection, NOAA's Product User Guide). None if it's over the horizon."""
    req, rpol, h = 6378137.0, 6356752.31414, 42164160.0
    phi, lam = math.radians(lat), math.radians(lon - sub_lon)
    phic = math.atan((rpol ** 2 / req ** 2) * math.tan(phi))
    rc = rpol / math.sqrt(1 - 0.00669438 * math.cos(phic) ** 2)
    sx = h - rc * math.cos(phic) * math.cos(lam)
    sy = -rc * math.cos(phic) * math.sin(lam)
    sz = rc * math.sin(phic)
    if h * (h - sx) < sy ** 2 + (req ** 2 / rpol ** 2) * sz ** 2:
        return None
    ext = 0.151872  # full-disk scan angle, radians
    x = math.asin(-sy / math.sqrt(sx * sx + sy * sy + sz * sz))
    y = math.atan(sz / sx)
    gx, gy = (x + ext) / (2 * ext), (ext - y) / (2 * ext)
    # keep the ring off the very edge of the disk, where it would be cut off or meaningless
    return (gx, gy) if 0.04 < gx < 0.96 and 0.04 < gy < 0.96 else None


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
            tick = int((time.time() + n * 15) // ROTATE_SECONDS)  # stagger so cards don't all flip at once
            card = dict(items[tick % len(items)])
            group = [c for c in items if card.get("group") and c.get("group") == card["group"]]
            if len(group) > 1:  # count within the card's own group: fire 2/5, waves 3/5 - not the whole slot
                card["note"] = f"{group.index(items[tick % len(items)]) + 1}/{len(group)}  .  " + card.get("note", "")
            cards[slot] = card
            ticks.append(tick % len(items))
        state["cards"] = cards
        globe = state.pop("globe", None)
        phase = 0
        if globe and state.get("focus") and time.time() % EVENT_CYCLE_SECONDS >= EVENT_CYCLE_SECONDS - GLOBE_SECONDS:
            state["image"], state["caption"], state["focus"] = globe[0], globe[1], None
            phase = 1
        state["version"] = (state["version"], tuple(ticks), phase)  # renderer redraws when any change
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
        water = self._safe(self._waters) or []
        fires, temp = self._safe(self._fires) or [], self._safe(self._world_temp)
        water = fires + ([temp] if temp else []) + water  # bottom slot: fires, world temp, groundwater
        if water:
            sets["water"] = water
        # Extra cards ride along in the existing slots so the screen keeps four cards:
        # quake slot also shows aurora (Kp) and solar wind; ocean slot also shows Arctic sea ice.
        space = [c for c in (self._safe(self._aurora), self._safe(self._solar_wind)) if c]
        if space and sets.get("quakes"):
            sets["quakes"] = sets["quakes"][:1] + space
        ice = self._safe(self._sea_ice)
        if ice and sets.get("buoy"):
            sets["buoy"] = [b for b in sets["buoy"] if b.get("title", "").startswith("OCEAN")] + [ice]

        # Hurricane first, then a big quake; if one's close-up has no imagery, try the next.
        focus, image, caption = None, None, None  # image = list of frames (one for a still)
        closeup = False
        for f in [x.get("focus") for x in (storms, quake) if x and x.get("focus")]:
            if f.get("kind") == "quake":
                # A quake has nothing to see up close (often open ocean): mark it on the live globe.
                image, caption = self._safe(lambda: self._full_disk(f)) or (None, None)
                if image is not None:
                    focus = f
                    break
            image, caption = self._safe(lambda: self._closeup(f)) or (None, None)
            if image is not None:
                focus, closeup = f, True
                break
        globe = None
        if closeup or focus is None:  # shown alone, or for the globe minutes between close-up loops
            globe = self._safe(lambda: self._full_disk(focus))
        if image is None and globe:
            image, caption = globe

        for items in sets.values():
            for c in items:
                t = c.get("title", "")
                kind = next((k for p, k in (("HURRICANE", "storm"), ("TROPICS", "storm"), ("EARTHQUAKES", "quakes"),
                                            ("AURORA", "aurora"), ("SOLAR", "solar"), ("OCEAN", "ocean"),
                                            ("ARCTIC", "ice"), ("EARTH'S", "temp"), ("FIRES", "fire"),
                                            ("WATER", "water")) if t.startswith(p)), None)
                if kind:
                    c["color"] = CARD_COLORS[kind]
                    c.setdefault("group", {"storm": "storm", "ocean": "ocean", "fire": "fire", "water": "water"}.get(kind))

        with self._lock:
            if image is not None:
                self._state["image"], self._state["caption"] = image, caption
            if globe and closeup:
                self._state["globe"] = globe
            else:
                self._state.pop("globe", None)
            self._state["focus"] = focus
            self._state["sets"] = sets
            self._state["version"] += 1

    # ---- images -----------------------------------------------------------------------
    def _full_disk(self, focus=None):
        """The whole globe from GOES East or West (they alternate each refresh). With a focus, use
        the satellite that can see it best and put a red ring on the spot - returns None if
        neither satellite can see it (the far side of the planet)."""
        if focus:
            seen = [(abs(focus["lon"] - GOES_SUBLON[n]), n) for n in GOES
                    if _geo_xy(focus["lat"], focus["lon"], GOES_SUBLON[n]) is not None]
            if not seen:
                return None
            name = min(seen)[1]
        else:
            name = list(GOES)[self._goes_turn % len(GOES)]
            self._goes_turn += 1
        img = Image.open(io.BytesIO(_get(GOES[name], timeout=60).content)).convert("RGB")
        n = img.width
        img = img.resize((self.size, self.size), Image.LANCZOS)
        caption = f"LIVE FROM SPACE  .  {name}  .  NOAA  .  {datetime.now(timezone.utc):%H:%M} UTC"
        if focus:
            gx, gy = _geo_xy(focus["lat"], focus["lon"], GOES_SUBLON[name])
            x, y = gx * self.size, gy * self.size
            d = ImageDraw.Draw(img)
            for r_, w in ((16, 3), (24, 2)):
                d.ellipse([x - r_, y - r_, x + r_, y + r_], outline=(255, 77, 77), width=w)
            caption = f"LIVE FROM SPACE . {focus['label']} . {name} . {datetime.now(timezone.utc):%H:%M} UTC"
        return [img], caption

    def _closeup(self, focus):
        """Worldview satellite close-up centered on the event, with a marker on it.
        Over GOES coverage this is a loop of the last LOOP_FRAMES frames (10 min apart), oldest
        first, so viewers watch the storm move instead of a near-identical still every 10 min."""
        lat, lon = focus["lat"], focus["lon"]
        half = 8.0
        bbox = f"{lat - half},{lon - half},{lat + half},{lon + half}"
        now = datetime.now(timezone.utc)

        def snap(layers, when, size):
            return _get(WORLDVIEW, timeout=60, params={
                "REQUEST": "GetSnapshot", "TIME": when, "BBOX": bbox, "CRS": "EPSG:4326",
                "LAYERS": layers, "FORMAT": "image/jpeg", "WIDTH": size, "HEIGHT": size}).content

        def fetch(layer, when):
            if layer.endswith("_ABI_GeoColor"):
                # Gap check on the infrared band, not the color image: the ocean at NIGHT is pure
                # black in GeoColor (that rejected every night frame of Hurricane Simon), but in
                # infrared it's gray day and night - only frames Worldview hasn't filled in yet are black.
                ir = snap(layer.replace("GeoColor", "Band13_Clean_Infrared"), when, 140)
                if len(ir) < 1500 or _missing_fraction(Image.open(io.BytesIO(ir)).convert("RGB")) > 0.05:
                    return None
            content = snap(f"{layer},Coastlines_15m", when, self.size)
            if len(content) < 20000:  # under ~20 KB = mostly-empty tile, no imagery yet
                return None
            img = Image.open(io.BytesIO(content)).convert("RGB")
            if not layer.endswith("_ABI_GeoColor") and _missing_fraction(img) > 0.05:
                return None  # polar-orbit swaths: gaps between passes are black
            return img

        if -150 <= lon <= -20:  # GOES geostationary coverage: a new frame every 10 min
            layer = "GOES-East_ABI_GeoColor" if lon > -105 else "GOES-West_ABI_GeoColor"
            source = "GOES-East" if lon > -105 else "GOES-West"
            # Worldview's GOES tiles lag by a variable amount (GOES-West was 40-100 min behind on
            # Oct 13 2026), so step back until a frame has actual imagery in it...
            newest = None
            for mins in (40, 70, 100, 130, 180, 240):
                t = now - timedelta(minutes=mins)
                t = t.replace(minute=t.minute // 10 * 10, second=0, microsecond=0)
                img = fetch(layer, t.strftime("%Y-%m-%dT%H:%M:%SZ"))
                if img is not None:
                    newest = (t, img)
                    break
            if newest is None:
                return None
            # ...then walk back from it for the rest of the loop (skipping any gappy frame).
            frames, times = [newest[1]], [newest[0]]
            for k in range(1, LOOP_FRAMES):
                t = newest[0] - timedelta(minutes=10 * k)
                img = self._safe(lambda: fetch(layer, t.strftime("%Y-%m-%dT%H:%M:%SZ")))
                if img is not None:
                    frames.append(img)
                    times.append(t)
            frames.reverse()
            stamp = f"{times[-1]:%H:%M}-{times[0]:%H:%M} UTC loop" if len(frames) > 1 else f"{times[0]:%H:%M} UTC"
        else:  # elsewhere: polar-orbit true color, one pass a day, so a still
            layer, source = "VIIRS_SNPP_CorrectedReflectance_TrueColor", "NASA VIIRS"
            frames, stamp = [], None
            for d in (1, 2):
                when = (now - timedelta(days=d)).strftime("%Y-%m-%d")
                img = fetch(layer, when)
                if img is not None:
                    frames, stamp = [img], when
                    break
            if not frames:
                return None
        c = self.size // 2
        for img in frames:
            ImageDraw.Draw(img).ellipse([c - 14, c - 14, c + 14, c + 14], outline=(255, 77, 77), width=3)
        return frames, f"FROM SPACE . {focus['label']} . {source} . {stamp}"

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
                     "label": f"Hurricane {s['name']}, {saffir(int(s['intensity']))}", "kind": "storm"}
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
            focus = {"lat": lat, "lon": lon, "label": f"M{big['properties']['mag']:.1f} earthquake", "kind": "quake"}
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

    def _aurora(self):
        """Planetary Kp index (0-9), every 3 hours for the last week. Kp 5+ is a geomagnetic storm."""
        rows = _get(KP_URL).json()
        v = [float(r["Kp"]) for r in rows if r.get("Kp") is not None]
        if len(v) < 9:
            return None
        kp = v[-1]
        level = next((f"G{g} storm" for g, t in ((5, 9), (4, 8), (3, 7), (2, 6), (1, 5)) if kp >= t), None)
        where = ("auroras deep into the US" if kp >= 7 else "auroras in the northern US" if kp >= 5
                 else "auroras near the Arctic Circle" if kp >= 3 else "quiet")
        # Kp sits near 0 when space is quiet, and FSR breaks near zero (it would show a red score at the
        # calmest moment), so only score it once the last day has real activity in it.
        score = fsr(v, 8) if sum(v[-8:]) / 8 >= 2 else None
        return {"title": "AURORA WATCH  .  SPACE WEATHER", "value": f"Kp {kp:.1f}" + (f"  .  {level}" if level else "  .  calm"),
                "score": score, "series": v, "note": f"{where}  .  NOAA, 3-hourly  .  24h stability"}

    def _solar_wind(self):
        """Solar wind speed from the active upstream spacecraft, every 10 minutes for the last day."""
        rows = [r for r in _get(SOLAR_WIND_URL, timeout=60).json() if r.get("active") and r.get("proton_speed")]
        rows.sort(key=lambda r: r["time_tag"])
        v = [float(r["proton_speed"]) for r in rows[-1440::10]]  # last 24 h, one reading per 10 min
        if len(v) < 20:
            return None
        return {"title": "SOLAR WIND  .  FROM THE SUN", "value": f"{v[-1]:.0f} km/s  ({v[-1] * 2237 / 1000:,.0f}k mph)",
                "score": fsr(v, 18), "series": v,
                "note": f"density {rows[-1].get('proton_density') or 0:.1f}/cm3  .  NOAA real time  .  3h stability"}

    def _sea_ice(self):
        """Arctic sea ice extent, last 90 days, ranked against the same date every year since 1979."""
        import csv
        rows = {}
        for r in csv.reader(io.StringIO(_get(SEA_ICE_URL, timeout=90).text)):
            try:
                rows[(int(r[0]), int(r[1]), int(r[2]))] = float(r[3])
            except (ValueError, IndexError):
                continue
        days = sorted(rows)
        last = days[-1]
        v = [rows[d] for d in days[-90:]]
        ref, prev = [], None
        for (y, m, d) in days[-90:]:  # same calendar days one year earlier (faint line)
            prev = rows.get((y - 1, m, d), prev)
            ref.append(prev)
        same = sorted(x for (y, m, d), x in rows.items() if (m, d) == last[1:])
        rank = same.index(rows[last]) + 1
        tag = "lowest on record for the date" if rank == 1 else f"#{rank} lowest for the date"
        return {"title": "ARCTIC SEA ICE  .  NSIDC", "value": f"{rows[last]:.2f} million km2  .  {tag}",
                "score": fsr(v, 14), "series": v, "ref": ref,
                "note": f"faint line = last year  .  #{rank} of {len(same)} years since 1979"}

    def _world_temp(self):
        """Earth's average air temperature (ERA5) for the last 90 days, ranked for the date since 1940."""
        series = _get(WORLD_TEMP_URL, timeout=90).json()
        years = {s["name"]: s["data"] for s in series if s["name"].isdigit()}
        now_year = max(years, key=int)
        cur = [x for x in years[now_year] if x is not None]
        prev = [x for x in years.get(str(int(now_year) - 1), []) if x is not None]
        v = (prev + cur)[-90:]
        doy = len(cur) - 1
        prev2 = [x for x in years.get(str(int(now_year) - 2), []) if x is not None]
        both = prev2 + prev
        end = len(prev2) + len(cur)  # same day-of-year, one year earlier
        ref = both[max(0, end - 90):end] if len(both) >= end else None
        same = sorted(((d[doy], y) for y, d in years.items() if len(d) > doy and d[doy] is not None), reverse=True)
        rank = [y for _, y in same].index(now_year) + 1
        tag = "warmest on record for the date" if rank == 1 else f"#{rank} warmest for the date"
        return {"title": "EARTH'S TEMPERATURE  .  WORLDWIDE", "value": f"{cur[-1]:.2f} C  .  {tag}",
                "score": fsr(v, 14), "series": v, "ref": ref,
                "note": f"faint line = last year  .  #{rank} of {len(same)} years since 1940"}

    def _fires(self):
        """Fire hotspots NASA's satellites saw each day for the last FIRE_DAYS days: one worldwide card,
        then the five busiest regions yesterday (fire 1/5 ... 5/5), each with its own 30-day line."""
        from dotenv import dotenv_values
        key = dotenv_values(os.path.join(ROOT, ".env")).get("FIRMS_MAP_KEY")
        if not key:
            return None
        import csv
        import json
        cache = json.load(open(FIRE_CACHE)) if os.path.exists(FIRE_CACHE) else {}
        regions = cache.get("_regions", {})  # day -> {region: hotspots}
        today = datetime.now(timezone.utc).date()
        days = [str(today - timedelta(n)) for n in range(FIRE_DAYS, 0, -1)]  # complete days only
        for day in days:
            # NRT days keep filling in for ~2 days, so the most recent two are always refetched
            if day in cache and day in regions and day < str(today - timedelta(2)):
                continue
            text = _get(FIRMS_AREA.format(key=key, day=day), timeout=120).text
            if not text.startswith("latitude"):
                continue
            rows = list(csv.DictReader(io.StringIO(text)))
            cache[day] = len(rows)
            tally = {}
            for r in rows:
                la, lo = float(r["latitude"]), float(r["longitude"])
                name = next((n for n, a, b, c, d in FIRE_REGIONS if a <= la <= b and c <= lo <= d), None)
                if name:
                    tally[name] = tally.get(name, 0) + 1
            regions[day] = tally
        cache["_regions"] = regions
        cache.pop("_top", None)
        os.makedirs(os.path.dirname(FIRE_CACHE), exist_ok=True)
        json.dump(cache, open(FIRE_CACHE, "w"))
        have = [d for d in days if d in cache and d in regions]
        if len(have) < 8:
            return None
        last = have[-1]
        world = [cache[d] for d in have]
        out = [{"title": "FIRES  .  WORLDWIDE", "value": f"{world[-1]:,} fire hotspots yesterday",
                "score": fsr(world, 7), "series": world, "group": None,  # no counter: regions are 1/5..5/5
                "note": "NASA FIRMS satellites  .  7-day stability"}]
        top5 = sorted(regions[last].items(), key=lambda kv: -kv[1])[:5]
        for rank, (name, n) in enumerate(top5, 1):
            v = [regions[d].get(name, 0) for d in have]
            share = n / world[-1] * 100 if world[-1] else 0
            score = fsr(v, 7) if min(v[-7:]) > 0 else None  # a zero day breaks FSR - show no score then
            out.append({"title": f"FIRES  .  {name.upper()}", "value": f"{n:,} hotspots yesterday  .  #{rank} on Earth",
                        "score": score, "series": v, "group": "fire",
                        "note": f"{share:.0f}% of the world's fires  .  NASA FIRMS"})
        return out

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
