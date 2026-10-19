# StabilityNetwork Shorts Playbook

What works for the channel, learned from ~110 Shorts (Sept to Oct 2026). Commands for every tool
are in **GENERATORS.md**. The morning digest (7 AM / 5 PM) lands in `output/digest/`.

---

## The rules

1. **Current only.** Every Short needs a reason it matters *this week*: a game tonight, a live storm,
   a new record, a release, a rising search. History-only charts flop, even with a perfect shape
   (Jujutsu Kaisen: under 2% completion).
2. **Your engine on raw data.** Feed real numbers straight into FSR. No outside composite stats
   (no Game Score, no someone-else's index). FSR is the measurement.
3. **Long series.** Hundreds of points. Never ~20.
4. **Your calculator format.** Line chart on top, sliding window below. No bar charts or rankings.
5. **Check the shape before charting** (see "What charts well").
6. **One video, every platform.** YouTube, TikTok (and Facebook if you keep it).

---

## What has worked (and the settings)

| Short | Data | Window | k | Result |
|---|---|---|---|---|
| RTX 5090 price shock | hand-collected street prices | — | — | all-time best |
| Demon Slayer (Infinity Castle #1 on Netflix) | Wikipedia weekly, 2017-2026 | 4 | 1 | 630 views first hour |
| JoJo (Steel Ball Run airing) | Wikipedia weekly, 10 yrs | 12 | 1 | ~1,000 |
| Attack on Titan | Wikipedia weekly, 10 yrs | 4 | 1 | 200+/hr overnight |
| Arctic sea ice | NSIDC monthly 1979-2026 | 12 | 2 | 2nd fastest start |
| Verlander career | strikeouts per start | 5 | 2 | 180 in 22 min |
| Chris Sale / Peralta / Williams / Henderson / Rasmussen | every pitch of one type | ~1 game | 0.5 | growing each time |
| Hurricane Isaias Parts 1-2 | NOAA buoy 42039 waves, hourly | 24 / 12 | 1 | beat everything that week |
| Big truck sales | FRED HTRUCKSSAAR monthly | 12 | 2 | steady on every platform |
| K-shaped economy | Wikipedia "Recession shapes" weekly | 12 | 2 | best on TikTok |
| Texas groundwater (NASA) | groundwater_gen.py texas_panhandle | 6 | 1 | the "stopped moving" angle |
| Drought (lower 48 + Tennessee) | drought_gen.py, weekly since 2000 / 2020 | 12 / 24 | 1 | great on TikTok; lower-48 flat chart missed on YouTube |
| Pitchers in October (Snell, Jax, Martinez, Messick) | pitch_velo_gen / mlb_pitcher_gen, playoffs included | ~1 game | 0.5 | best TikTok numbers (250-270) |
| Indonesia fires (NASA FIRMS) | fire_gen.py --preset indonesia, monthly since 2001 | 12 | 1 | strong; Wikipedia 3-6x during the season |

**Flopped:** single stocks, diesel, abstract econ (lipstick effect), the 5th AI audit in a row (Discord),
anime with nothing new happening (JJK), old national totals, interest rates (mortgage, 10-yr: 50-100 views),
niche anime (check AniList "on lists" first - 50k+ or skip; Vampire Hunter D had ~900 watching).

---

## What charts well (check before you chart)

- **Good:** prices, sales and counts of one specific thing (trucks, containers, cocoa, pitches,
  waves, incidents). Several spikes of similar size. A full rise-peak-fall.
- **Reads flat (skip):** national totals - jobs, GDP, population, income, CPI, money supply.
  They're huge and move ~1% a month, so the window sits at 95-99%.
- **Breaks the engine:** anything that crosses or touches zero (rates near 0%, anomalies, % changes).
- **One giant old spike dwarfs today's story** (Kamchatka quake, Tokyo Revengers 2021): look for a
  version without it (a regional cut, a later start date).
- **Flat line, spike at the end:** avoid, unless it's a live event and you're doing Part 1 of a series.
- **When the engine is flat at an extreme, the flatness is the story**: groundwater at a 23-year low
  and its most stable ever = "it stopped moving."

**What the engine actually is:** FSR = 100 x e^(-k x |CV|), CV = standard deviation / mean of the window.
It scores swings relative to the average. That's why near-zero data breaks it (tiny mean), why huge
totals read flat (tiny relative swings), and why a big window smooths things.

- **Window rule of thumb:** points / 25 for long daily series (e.g. 5,903 days -> ~236, use a trading year).
- **Calculator limit: 5,000 points per upload.** Longer daily series: start later or go weekly.
- **Zeros:** a wider window (Tennessee drought at 24) or a later start date can get around them.
- **Verify the k:** match the chart's overall "Score:" against the generator's printout.

---

## NASA data (Earthdata token)

- **groundwater_gen.py** - underground water for any point on Earth, monthly since 2003.
- **rain_gen.py** - satellite rainfall every 30 minutes (hours behind real time) or daily.
  Best for a live storm or monsoon *caused by rain* hitting a named city. Not for floods caused by
  dam/landslide breaks or glacier collapses - rain data won't show those.
- Say "measured from space by NASA" / "NASA satellite estimate", not "this well" or "this gauge".

---

## Script formula (~40 words, ~16 sec)

1. What it is, and how long: "Every sweeper Gavin Williams threw this season: 852."
2. The normal / the big moment with a real number: "His shakiest stretch: late June, 98.88%."
3. The twist or the now: "Tonight, the playoffs, and he's at 99.47."
4. A question or what's next: "Can the sweeper carry Cleveland?"

Read the overall **Score** on your chart screenshot to confirm the k before quoting numbers.

---

## Captions

- **YouTube title:** the hook, not the method. Keep "FSR" jargon out of titles.
- **Description:** what the data is + source + window/k, the 2-3 key numbers, then
  "Score any time series for stability at predictability-api.com".
- **TikTok:** 1-2 lines + a question people can answer ("What are you paying for gas?") + 3-5
  hashtags. Link goes in your bio, not the caption.
- **Add a Japanese/Spanish line** when it fits (Japanese stars and anime: 山本由伸, 鬼滅の刃;
  Panama/Mexico: #terremoto, #huracan).
- **Pin a question comment** right after posting. Comments push a Short past the ~1,000 wall.

---

## Platform notes

- **YouTube** is the strongest. Good Shorts reliably get 200-400; the best break 1,000.
- **TikTok:** post 1-2 a day, hours apart. Bursts of several in a row got the account throttled to
  0 views for a day. Upload the original file, not one downloaded from YouTube.
- **Facebook:** weak for most topics (AI audits were the exception, then faded).
- **AI label:** if a background photo was edited with Google Photos AI tools, YouTube may tag the
  video "altered content." Use unedited photos or screenshots.
- **Live tragedies:** keep it factual, add a respectful line, and never post a "start to finish"
  storm chart while people are still without power.

---

## Daily routine

1. Read the digest (7 AM / 5 PM), **section 0 "Ready to chart" first** - files are already saved and
   ranked by how viral they are (Wikipedia spike + YouTube rising). Items shown in the last 3 days are
   held back unless their numbers changed. Then 12 (Earth/NASA), 13 (sports tonight), 14 (Steam +
   Netflix), 1 (engine picks, with a "what it is" column), 11 (rising searches).
2. Pick something **current** with long data behind it.
3. Run the generator, chart it in the calculator, screenshot.
4. Write the script with the numbers from the screenshot's settings.
5. Post everywhere; pin a question comment.

---

## Accounts & keys (`.env`, never paste keys in chat)

FRED_API_KEY, EIA_API_KEY, KAGGLE_API_TOKEN, NASA_API_KEY, CENSUS_API_KEY, EARTHDATA_TOKEN
(expires **Dec 12, 2026 10:27 PM MT** - make a new one at urs.earthdata.nasa.gov, max 2 active),
FIRMS_MAP_KEY (NASA fires), TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET (twitch_recorder), TWITCH_STREAM_KEY.

---

## Tools added Oct 13-19, 2026 (details in GENERATORS.md)

- **fire_gen.py** - NASA FIRMS fire hotspots, any region, monthly since 2001 (first run of a region ~35 min).
- **drought_gen.py** - US Drought Monitor, lower 48 or any state, weekly since 2000.
- **flu_gen.py** - CDC flu-like illness, weekly since 1997. **tornado_gen.py** - US tornadoes per month since 1950.
- **nfl_gen.py** - every game since 1999 from nflverse (multi-season). The older **nfl_data_gen.py** scrapes
  Pro-Football-Reference one season at a time.
- **nba_data_gen.py** - auto-detects the season, combines the last 3 (regular season + playoffs).
- **pitch_velo_gen.py / mlb_pitcher_gen.py** - now include postseason games.
- **twitch_recorder.py** - snapshots Twitch viewers every 10 min (register_twitch_task.ps1 schedules it);
  `--chart <channel>`, `--chart "<game>" --game`, `--top`. History starts when the recorder starts.
- **Steam** (in the digest): SteamCharts monthly players since 2012 for the top 50 games; combine
  editions (GTA V = Legacy 271590 + Enhanced 3240220).
- **Earth Watch stream** - globe + 4 rotating card slots: hurricanes; quakes/aurora/solar wind; ocean
  buoys/sea ice; fires (worldwide + top 5 regions)/world temperature/groundwater. Restart the stream
  (Ctrl+C, rerun run_stream.ps1) after code changes. `-Light` = 15 fps for using the PC at the same time.
- **Stream notes:** 750k video + 64k audio fits the Verizon upload; a full C: drive (CoinPoker filled
  %TEMP% with 25 MB Firefox-history copies) stalls everything - check free space first.
