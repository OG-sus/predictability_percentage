# Twitch channel copy - FSR Earth Watch

Everything to paste into twitch.tv/stabilitynetwork for the Earth Watch stream.
YouTube: youtube.com/@PredictabilityCalculator (channel ID UClyK_yir0DBphTOKZ9eL0hA).

---

## Stream title (Creator Dashboard > Stream Manager > Edit Stream Info, max 140)

```
🌍 LIVE Earth from space 24/7 · hurricanes, earthquakes & ocean waves, scored live · !fsr
```

**Category:** Science & Technology

**Tags** (max 10, no spaces):
```
EarthFromSpace  Hurricane  Earthquake  Weather  NASA  Satellite  Ocean  Science  AlwaysOn  English
```

---

## Bio (Settings > Channel > Profile, max 300)

```
Earth, live from space, 24/7. NOAA and NASA satellites plus live hurricane, earthquake, ocean buoy and groundwater data, each scored in real time by FSR: an engine that measures how stable any data is. New Shorts daily on YouTube. predictability-api.com
```

---

## Panels (Channel page > About > Edit panels)

### 1. What am I watching?
```
A live view of Earth from NOAA's GOES weather satellites, about 22,000 miles up. The picture refreshes every 10 minutes and switches between the East and West satellites.

When something big happens (a hurricane, or an M6.5+ earthquake), the view zooms in on it and a red LIVE EVENT badge appears.

On the right: live data cards, each with a stability score.
```

### 2. What does the % mean?
```
Every card shows an FSR score: how stable that data has been lately.

🟢 80-100%: steady. Normal, predictable behavior.
🟡 60-79%: shifting. Something's changing.
🔴 under 60%: unstable. Big swings right now.

A hurricane gaining strength fast, waves building before a storm, or a burst of earthquakes all pull the score down. Steady conditions push it up.

Fun case: groundwater can score near 100% at a record low. It isn't recovering, it's just stuck.
```

### 3. The cards
```
🌀 STORMS: the strongest active storms (NOAA National Hurricane Center), rotating.
🌍 EARTHQUAKES: every M4.5+ quake worldwide in the last 24h (USGS).
🌊 OCEAN: the 5 buoys with the biggest waves on Earth right now (NOAA). During a hurricane, the buoy nearest the storm comes first.
💧 WATER: underground water in U.S. drought regions, measured from space by NASA's GRACE satellites.
```

### 4. Where the data comes from
```
All public, all live:
• NOAA GOES-19 & GOES-18 satellites
• NASA Worldview satellite close-ups
• NOAA National Hurricane Center
• USGS Earthquake Hazards Program
• NOAA National Data Buoy Center
• NASA GLDAS / GRACE groundwater

The stability scores are ours: the FSR engine at predictability-api.com.
```

### 5. Score your own data
```
The same engine on this stream can score anything that changes over time: prices, sales, sensor readings, player stats, website traffic.

Try it free at predictability-api.com
```

### 6. YouTube
```
Daily Shorts: pitchers' fastballs, hurricanes, anime, prices, all run through the stability engine.

youtube.com/@PredictabilityCalculator
```

### 7. Support the stream
```
Earth Watch runs 24/7 on live satellite and sensor data. Follows, subs and bits keep it on the air and help pay for the data servers behind it.

Want the stability engine for your own business or project? That supports it too: predictability-api.com
```

### 8. X / Twitter
Keep your existing Twitter timeline panel (the extension), and set its header image to `08_twitter.png`.

**Remove the old panels:** "The Proof (Technical Validation) The Math" and "Get the Ticker". They describe
the old ticker stream and the OBS kit, not Earth Watch.

**Panel images:** run `python stream_infra/make_panels.py` and upload `output/twitch_panels/01-08*.png`,
one per panel in the order above (Edit panels > Image > upload). Rerun it any time for a fresh globe.

---

## Chat commands (Nightbot, free)

Setup: go to nightbot.tv, log in with Twitch, click **Join Channel**, then type `/mod nightbot`
in your chat. Add each command by pasting the line into your own chat:

```
!commands add !fsr FSR scores how stable data has been lately. 80%+ = steady, 60-79% = shifting, under 60% = unstable. Same engine you can use on your own data: predictability-api.com
!commands add !earth Live Earth from NOAA's GOES-19 (East) and GOES-18 (West) weather satellites, about 22,000 miles up. New image every 10 min. Big storms and quakes get a close-up.
!commands add !storm The storm card rotates through the strongest active storms, live from the National Hurricane Center. Track maps: nhc.noaa.gov
!commands add !buoy The ocean card shows the 5 buoys with the biggest waves on Earth right now, from NOAA's buoy network. During a hurricane, the buoy nearest the storm goes first. ndbc.noaa.gov
!commands add !water Groundwater for U.S. drought regions, measured from space by NASA. Several are at their lowest in 23 years.
!commands add !data Everything here is live public data: NOAA, NASA, USGS. The stability scores come from the FSR engine at predictability-api.com
!commands add !site predictability-api.com: score any time series for stability, free to try.
!commands add !youtube Daily Shorts on YouTube: youtube.com/@PredictabilityCalculator
```

Optional timer (Nightbot > Timers): post `!fsr`'s text every 30 minutes, if at least 5 chat lines have gone by.

---

## Later: commands that answer with what's on screen right now

Nightbot can read a web address with `$(urlfetch https://...)`. If the website got a small
endpoint like `predictability-api.com/stream/now` that the stream updates, `!storm` and `!buoy`
could reply "Hurricane Simon, Cat 1, 92 mph, FSR 97%" live. That needs a few lines in api.py
plus the stream posting its current cards.
