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
import os
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
DEFAULT_BUOY = ("42001", "Mid-Gulf buoy 42001")
GROUNDWATER_FILE = os.path.join(ROOT, "output", "groundwater_texas_panhandle.txt")

FOCUS_STORM_KT = 64      # hurricanes (64 kt+) take over the main image
FOCUS_QUAKE_MAG = 6.5    # so do M6.5+ quakes in the last 24 hours


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


class EarthWatch:
    def __init__(self, image_size=560):
        self.size = image_size
        self._lock = threading.Lock()
        self._state = {"image": None, "caption": "Loading satellite view...", "focus": None,
                       "cards": {}, "version": 0}
        self._goes_turn = 0

    # ---- public -----------------------------------------------------------------------
    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def refresh(self):
        storms, quake = self._safe(self._storms), self._safe(self._quakes)
        cards = dict(self.snapshot()["cards"])
        if storms is not None:
            cards["storm"] = storms["card"]
        if quake is not None:
            cards["quakes"] = quake["card"]
        buoy = self._safe(self._buoy)
        if buoy is not None:
            cards["buoy"] = buoy
        water = self._safe(self._groundwater)
        if water is not None:
            cards["water"] = water

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
            self._state["cards"] = cards
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
            for mins in (40, 70, 100, 150):
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
            if len(r.content) >= 20000:  # under ~20 KB = mostly-empty tile, no imagery yet
                break
        else:
            return None
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        d = ImageDraw.Draw(img)
        c = self.size // 2
        d.ellipse([c - 14, c - 14, c + 14, c + 14], outline=(255, 77, 77), width=3)
        return img, f"FROM SPACE  .  {focus['label']}  .  {source} via NASA Worldview"

    # ---- sensor cards -----------------------------------------------------------------
    def _storms(self):
        active = _get(NHC_CURRENT).json().get("activeStorms", [])
        if not active:
            return {"card": {"title": "TROPICS", "value": "No active storms", "score": None, "series": []}}
        s = max(active, key=lambda x: int(x.get("intensity") or 0))
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
        card = {"title": f"HURRICANE WATCH  .  {s['name'].upper()}" if kt >= 64 else f"TROPICS  .  {s['name'].upper()}",
                "value": f"{saffir(kt)}  {kt} kt / {round(kt * 1.15078)} mph  .  {s['pressure']} mb",
                "score": fsr(winds, 4), "series": winds[-40:],
                "note": f"{len(active)} active storm{'s' if len(active) != 1 else ''}  .  24h stability"}
        focus = None
        if kt >= FOCUS_STORM_KT:
            focus = {"lat": float(s["latitudeNumeric"]), "lon": float(s["longitudeNumeric"]),
                     "label": f"Hurricane {s['name']}, {saffir(kt)}"}
        return {"card": card, "focus": focus}

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

    def _buoy(self):
        station, label = DEFAULT_BUOY
        lines = _get(f"https://www.ndbc.noaa.gov/data/realtime2/{station}.txt").text.splitlines()
        hdr = lines[0].lstrip("#").split()
        i = hdr.index("WVHT")
        seen, v = set(), []
        for row in reversed([ln.split() for ln in lines[2:]]):
            if row[i] != "MM" and tuple(row[:4]) not in seen:
                seen.add(tuple(row[:4]))
                v.append(float(row[i]))
        v = v[-72:]
        return {"title": f"OCEAN  .  {label.upper()}", "value": f"Waves {v[-1]:.1f} m  ({v[-1] * 3.281:.0f} ft)",
                "score": fsr(v, 24), "series": v, "note": "NOAA, hourly  .  24h stability"}

    def _groundwater(self):
        if not os.path.exists(GROUNDWATER_FILE):
            return None
        v = [float(x) for x in open(GROUNDWATER_FILE).read().split(",")]
        low = v[-1] <= min(v) * 1.005
        return {"title": "WATER  .  TEXAS PANHANDLE", "value": f"Groundwater {v[-1]:.0f} mm"
                + ("  .  23-yr low" if low else ""), "score": fsr(v, 6), "series": v,
                "note": "NASA, measured from space  .  6-mo stability"}

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
