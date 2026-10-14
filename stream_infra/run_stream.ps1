<#
run_stream.ps1 - Volatility Radar local 24/7 stream runner

Pipes stream_infra\stream_renderer.py (a Python-rendered frame stream -
header, logo, color-coded ticker grid, subscribe banner, all composited
in Pillow) straight into ffmpeg's stdin, muxed with an audio track, and
pushes to Twitch/YouTube in a loop so a crash or network blip doesn't
kill the stream for good.

This replaced an earlier version that used ffmpeg's drawtext(reload=1)
reading a live-updating text file - ffmpeg's own docs warn that reload
"may fail" without perfectly atomic updates, and it reloads 30x/second,
which on Windows occasionally hit a real (if rare) file-sharing
violation that's fatal to ffmpeg. Piping fully-rendered frames removes
the shared file entirely, so that failure mode can't happen.

Setup before first run:
  1. Put your stream key(s) in .env as TWITCH_STREAM_KEY and/or
     YOUTUBE_STREAM_KEY (YouTube Studio > Go Live > Stream key,
     or Twitch > Creator Dashboard > Settings > Stream). Never put
     the key directly in this script - it's not gitignored.
  2. Edit $Platform below to "twitch", "youtube", or "both". "both"
     uses ffmpeg's tee muxer to push one encode to each platform at
     once (not two separate encodes) - roughly doubles the upload
     bandwidth needed versus a single platform, since it's the same
     bitrate sent twice.
  3. Optionally set $MusicFolder to a folder of mp3/wav files -
     loops and plays them back to back. Leave empty for silence.
     IMPORTANT: OBS isn't in this pipeline, so nothing filters your
     audio for you anymore - only put tracks in here that are
     explicitly cleared for 24/7 streaming on Twitch/YouTube (e.g.
     StreamBeats by Harris Heller, streambeats.com - free, made for
     exactly this). Random downloaded music WILL get claimed/muted.

Run:
    powershell -File stream_infra\run_stream.ps1
#>

# -Light: for when you're using the PC too. 15 fps (a quarter less work) and normal priority,
# so the stream gets a fair share of the CPU instead of whatever is left over.
#     powershell -ExecutionPolicy Bypass -File stream_infra\run_stream.ps1 -Light
param([switch]$Light)

$ErrorActionPreference = "Stop"

# --- CONFIG -----------------------------------------------------
$Platform   = "twitch"    # "twitch", "youtube", or "both"
$MusicFolder = Join-Path $PSScriptRoot "music"  # drop .mp3/.wav files here; empty folder = silence
$MusicVolumeDb = "-22dB"  # background level, not foreground - tune this if it's still too loud/quiet
$Resolution = "1280x720"
$FrameRate  = 20          # a ticker board doesn't need 30; renderer reads this via STREAM_FPS
if ($Light) { $FrameRate = 15 }
$VideoBitrate = "1100k"   # Verizon home internet sustains ~1.4 Mbps to Twitch (Oct 13 test), so ~1.2 total leaves headroom
$Encoder    = "qsv"       # "qsv" = Intel Quick Sync (Iris Xe, near-zero CPU), "x264" = software fallback
# ------------------------------------------------------------------

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Ffmpeg   = "C:\Users\RMDon\AppData\Local\Microsoft\WinGet\Packages\BtbN.FFmpeg.GPL.7.1_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-n7.1.5-12-g1fdbca85aa-win64-gpl-7.1\bin\ffmpeg.exe"
$Python   = "python"
$Renderer = Join-Path $PSScriptRoot "stream_renderer.py"

# --- Load stream key from .env (never hardcode it here - this script isn't gitignored) ---
$EnvFile = Join-Path $RepoRoot ".env"
$EnvVars = @{}
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $EnvVars[$matches[1]] = $matches[2].Trim()
        }
    }
}

function Get-RtmpUrl {
    param($platform, $key)
    if ($platform -eq "twitch") { "rtmp://live.twitch.tv/app/$key" }
    else { "rtmp://a.rtmp.youtube.com/live2/$key" }
}

$TwitchKey = $EnvVars["TWITCH_STREAM_KEY"]
$YoutubeKey = $EnvVars["YOUTUBE_STREAM_KEY"]

# --- Output target(s): one platform (-f flv) or both via ffmpeg's tee muxer ---
# onfail=ignore on each branch means one platform having a hiccup doesn't
# take down the other's connection along with it.
if ($Platform -eq "both") {
    if ([string]::IsNullOrWhiteSpace($TwitchKey)) {
        Write-Error "Set TWITCH_STREAM_KEY in .env before running with `$Platform = 'both'."
        exit 1
    }
    if ([string]::IsNullOrWhiteSpace($YoutubeKey)) {
        Write-Error "Set YOUTUBE_STREAM_KEY in .env before running with `$Platform = 'both'."
        exit 1
    }
    $twitchUrl = Get-RtmpUrl "twitch" $TwitchKey
    $youtubeUrl = Get-RtmpUrl "youtube" $YoutubeKey
    $OutputArgs = @("-f", "tee", "[f=flv:onfail=ignore]$twitchUrl|[f=flv:onfail=ignore]$youtubeUrl")
} else {
    $key = if ($Platform -eq "twitch") { $TwitchKey } else { $YoutubeKey }
    if ([string]::IsNullOrWhiteSpace($key)) {
        $envVarName = if ($Platform -eq "twitch") { "TWITCH_STREAM_KEY" } else { "YOUTUBE_STREAM_KEY" }
        Write-Error "Set $envVarName in .env before running (platform is currently set to '$Platform')."
        exit 1
    }
    $OutputArgs = @("-f", "flv", (Get-RtmpUrl $Platform $key))
}

Set-Location $RepoRoot

# --- One copy at a time ---
# A second copy is actively harmful: each time it fails (Twitch only takes one connection per key)
# its cleanup below kills EVERY stream_renderer.py on the machine, including the live one's, which
# leaves the live ffmpeg streaming music over a black screen. A named mutex makes copy #2 bail out.
$script:StreamMutex = New-Object System.Threading.Mutex($false, "Global\FSRStreamRunner")
try { $gotMutex = $script:StreamMutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $gotMutex = $true }
if (-not $gotMutex) {
    Write-Error "The stream is already running in another window (or the scheduled task). Close that one first."
    exit 1
}

# --- Audio source: your music folder on loop, or silence ---
$audioInput = $null
if ($MusicFolder -and (Test-Path $MusicFolder)) {
    $tracks = Get-ChildItem $MusicFolder -Include *.mp3, *.wav -File -Recurse | Sort-Object { Get-Random }
    if ($tracks.Count -gt 0) {
        $playlistPath = Join-Path $RepoRoot "stream_infra\playlist.txt"
        $lines = $tracks | ForEach-Object {
            $p = ($_.FullName -replace '\\', '/') -replace "'", "'\''"
            "file '$p'"
        }
        # No BOM: Windows PowerShell's Set-Content -Encoding UTF8 prepends one, and ffmpeg's
        # concat demuxer then reads line 1 as "<BOM>file" -> "unknown keyword 'file'".
        [System.IO.File]::WriteAllLines($playlistPath, [string[]]$lines, (New-Object System.Text.UTF8Encoding $false))
        Write-Output "Looping $($tracks.Count) track(s) from $MusicFolder"
        $audioInput = @("-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", $playlistPath)
    } else {
        Write-Warning "No .mp3/.wav files found in $MusicFolder - streaming silent."
    }
}
if (-not $audioInput) {
    $audioInput = @("-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100")
}

$env:STREAM_FPS = $FrameRate

# libx264 on this laptop's 15W i7 is what caused the lag and the slow
# drift to ~0.5x speed after hours (sustained load -> thermal throttling).
# Quick Sync does the encode on the Iris Xe iGPU instead, like OBS does.
if ($Encoder -eq "qsv") {
    $videoCodecArgs = @("-c:v", "h264_qsv", "-preset", "veryfast", "-pix_fmt", "nv12")
} else {
    $videoCodecArgs = @("-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p")
}

# Below-normal priority is inherited by the python + ffmpeg children, so
# anything you're doing on the machine always wins over the stream.
(Get-Process -Id $PID).PriorityClass = $(if ($Light) { "Normal" } else { "BelowNormal" })

Write-Output "Streaming to $Platform at $Resolution/${FrameRate}fps via $Encoder ..."
# Backoff so a flaky connection doesn't hammer Twitch/YouTube with rapid
# reconnects (bad for their ingest servers, and repeated short online/offline
# flips risk re-triggering "went live" notifications to your followers).
# A run that survives 2+ minutes is treated as healthy and resets the backoff.
$backoffSeconds = 5
$maxBackoffSeconds = 60
while ($true) {
    $ffmpegArgs = @(
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", $Resolution, "-r", $FrameRate, "-i", "-"
    ) + $audioInput + @(
        "-map", "0:v", "-map", "1:a"
    ) + $videoCodecArgs + @(
        "-b:v", $VideoBitrate, "-maxrate", $VideoBitrate, "-bufsize", "2200k",
        "-g", ($FrameRate * 2), "-r", $FrameRate,
        "-af", "volume=$MusicVolumeDb",
        "-c:a", "aac", "-b:a", "96k",
        "-shortest"   # renderer died -> end the stream so the loop restarts it (the music input never ends on its own)
    ) + $OutputArgs
    $runStart = Get-Date
    # Pipe through cmd, not PowerShell. A PowerShell pipe between two native
    # programs relays every byte itself (~55 MB/s of raw frames = wasted CPU),
    # and when ffmpeg exits it never closes the renderer's end - python just
    # blocks forever on its next write, which is what left an orphaned
    # renderer running after the -10054 dropped connection. A cmd pipe is a
    # real OS pipe: ffmpeg exiting gives python a broken pipe and it quits.
    $quoted = ($ffmpegArgs | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $pipeline = "`"$Python`" `"$Renderer`" | `"$Ffmpeg`" -hide_banner $quoted"
    try {
        cmd /c "`"$pipeline`""
    } catch {
        Write-Warning "Pipeline error: $($_.Exception.Message)"
    }
    # Belt and braces: never let a stale renderer outlive its ffmpeg.
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*stream_renderer.py*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $ranFor = (Get-Date) - $runStart

    if ($ranFor.TotalSeconds -ge 120) {
        $backoffSeconds = 5   # that was a healthy run — reset backoff
    } else {
        $backoffSeconds = [Math]::Min($backoffSeconds * 2, $maxBackoffSeconds)
    }

    Write-Warning "Stream pipeline exited after $([int]$ranFor.TotalSeconds)s. Restarting in ${backoffSeconds}s... (Ctrl+C to stop)"
    Start-Sleep -Seconds $backoffSeconds
}
