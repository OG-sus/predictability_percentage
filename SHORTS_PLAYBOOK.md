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

**Flopped:** single stocks, diesel, abstract econ (lipstick effect), the 5th AI audit in a row (Discord),
anime with nothing new happening (JJK), old national totals.

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

1. Read the morning digest: section 2 (storms), 7 (anime), 11 (rising searches), plus tonight's
   MLB/NBA/NFL starters.
2. Pick something **current** with long data behind it.
3. Run the generator, chart it in the calculator, screenshot.
4. Write the script with the numbers from the screenshot's settings.
5. Post everywhere; pin a question comment.

---

## Accounts & keys (`.env`, never paste keys in chat)

FRED_API_KEY, EIA_API_KEY, KAGGLE_API_TOKEN, NASA_API_KEY, CENSUS_API_KEY, EARTHDATA_TOKEN
(expires **Dec 12, 2026 10:27 PM MT** - make a new one at urs.earthdata.nasa.gov, max 2 active).
