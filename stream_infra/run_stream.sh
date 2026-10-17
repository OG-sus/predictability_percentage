#!/usr/bin/env bash
# run_stream.sh - Linux/VPS version of run_stream.ps1 (same pipeline, software encode).
#
# A data-center connection doesn't drop like cellular, and the stream keeps running with
# your PC off. Same idea as the Windows script: stream_renderer.py pipes raw frames into
# ffmpeg, which pushes to Twitch/YouTube, in a loop with backoff so a crash or blip recovers.
#
# Setup (once, on the VPS):
#   apt install -y ffmpeg fonts-dejavu-core
#   stream keys go in the repo's .env as TWITCH_STREAM_KEY / YOUTUBE_STREAM_KEY
#   optional: copy cleared tracks (StreamBeats) into stream_infra/music/ - empty = silence
#   then install the service: see stream_infra/fsr-stream.service
#
# Run by hand:  bash stream_infra/run_stream.sh

# --- CONFIG -------------------------------------------------------
PLATFORM="${STREAM_PLATFORM:-twitch}"   # "twitch", "youtube", or "both"
RESOLUTION="1280x720"
FRAME_RATE=20
VIDEO_BITRATE="1500k"   # Earth Watch is mostly still images + the ticker; 1500k looks clean
MUSIC_VOLUME_DB="-22dB"
# ------------------------------------------------------------------

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
cd "$REPO" || exit 1
PYTHON="${PYTHON:-$REPO/venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON=python3

# Read only the two stream keys from .env (never hardcode them here - this file is in git)
env_get() { grep -E "^\s*$1\s*=" "$REPO/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' | xargs; }
TWITCH_KEY="$(env_get TWITCH_STREAM_KEY)"
YOUTUBE_KEY="$(env_get YOUTUBE_STREAM_KEY)"
TWITCH_URL="rtmp://live.twitch.tv/app/$TWITCH_KEY"
YOUTUBE_URL="rtmp://a.rtmp.youtube.com/live2/$YOUTUBE_KEY"

case "$PLATFORM" in
  both)
    [ -n "$TWITCH_KEY" ] && [ -n "$YOUTUBE_KEY" ] || { echo "Set TWITCH_STREAM_KEY and YOUTUBE_STREAM_KEY in .env" >&2; exit 1; }
    OUTPUT=(-f tee "[f=flv:onfail=ignore]$TWITCH_URL|[f=flv:onfail=ignore]$YOUTUBE_URL") ;;
  youtube)
    [ -n "$YOUTUBE_KEY" ] || { echo "Set YOUTUBE_STREAM_KEY in .env" >&2; exit 1; }
    OUTPUT=(-f flv -rw_timeout 20000000 "$YOUTUBE_URL") ;;
  *)
    [ -n "$TWITCH_KEY" ] || { echo "Set TWITCH_STREAM_KEY in .env" >&2; exit 1; }
    OUTPUT=(-f flv -rw_timeout 20000000 "$TWITCH_URL") ;;
esac

# --- Audio: music folder on loop, or silence ---
AUDIO=(-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100)
PLAYLIST="$HERE/playlist.txt"
if [ -d "$HERE/music" ]; then
  find "$HERE/music" -type f \( -iname '*.mp3' -o -iname '*.wav' \) | shuf \
    | sed "s/'/'\\\\''/g; s/.*/file '&'/" > "$PLAYLIST"
  if [ -s "$PLAYLIST" ]; then
    echo "Looping $(wc -l < "$PLAYLIST") track(s)"
    AUDIO=(-f concat -safe 0 -stream_loop -1 -i "$PLAYLIST")
  fi
fi

export STREAM_FPS=$FRAME_RATE
echo "Streaming to $PLATFORM at $RESOLUTION/${FRAME_RATE}fps, $VIDEO_BITRATE (libx264) ..."

# Same backoff as the Windows script: a run that survives 2+ minutes resets it.
backoff=5
while true; do
  start=$(date +%s)
  "$PYTHON" "$HERE/stream_renderer.py" | ffmpeg -hide_banner -loglevel warning \
    -f rawvideo -pix_fmt rgb24 -s "$RESOLUTION" -r "$FRAME_RATE" -i - \
    "${AUDIO[@]}" -map 0:v -map 1:a \
    -c:v libx264 -preset veryfast -tune stillimage -pix_fmt yuv420p \
    -b:v "$VIDEO_BITRATE" -maxrate "$VIDEO_BITRATE" -bufsize 3000k \
    -g $((FRAME_RATE * 2)) -r "$FRAME_RATE" \
    -af "volume=$MUSIC_VOLUME_DB" -c:a aac -b:a 128k -shortest \
    "${OUTPUT[@]}"
  pkill -f "$HERE/stream_renderer.py" 2>/dev/null   # never leave a stale renderer behind
  ran=$(( $(date +%s) - start ))
  if [ "$ran" -ge 120 ]; then backoff=5; else backoff=$(( backoff * 2 > 60 ? 60 : backoff * 2 )); fi
  echo "Stream exited after ${ran}s. Restarting in ${backoff}s..." >&2
  sleep "$backoff"
done
