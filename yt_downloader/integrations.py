"""
integrations.py  —  THE INTEGRATION LAYER
==========================================
This module is the ONLY part of our application that talks to the outside
world (YouTube, through the yt-dlp library).

WHY isolate it here?
    If YouTube changes, or we swap yt-dlp for a different library one day,
    THIS is the only file we have to touch. Our menu, printing, and logic
    stay untouched. This is the "Single Responsibility Principle".

STRUCTURE (top to bottom):
    fetch_video_info()       - PUBLIC : metadata for one video
    _quality_label()         - helper : filename label for a quality
    _build_options()         - helper : the yt-dlp settings shared by all downloads
    _download_with_retries() - helper : run a download, retrying on transient blips
    download_video()         - PUBLIC : download ONE video
    download_playlist()      - PUBLIC : download an ENTIRE playlist

Functions starting with "_" follow a Python CONVENTION meaning "internal helper,
not meant to be called from outside this file." They let download_video and
download_playlist SHARE logic instead of copy-pasting it — the DRY principle
(Don't Repeat Yourself).
"""

# Standard-library module — we use it to pause between retry attempts.
import time

# The third-party library that actually talks to YouTube.
import yt_dlp


def fetch_video_info(url: str) -> dict:
    """
    Ask YouTube for information about a video WITHOUT downloading it.

    Parameters
    ----------
    url : str
        A full YouTube video URL, e.g. "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    Returns
    -------
    dict
        A dictionary of metadata: title, uploader, duration, view_count, etc.
    """
    options = {
        "quiet": True,          # don't print yt-dlp's own noisy progress logs
        "no_warnings": True,    # suppress warning spam so our output stays clean
        "skip_download": True,  # IMPORTANT: we only want info, not the video file
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    return info


def _quality_label(quality: str) -> str:
    """
    Return the text we stamp into the filename for a given quality.
      - "audio"       -> literally "audio" (audio has no resolution)
      - anything else -> "%(height)sp", a yt-dlp placeholder that becomes the
                         ACTUAL downloaded resolution (e.g. "1080p", "2160p").
    """
    if quality == "audio":
        return "audio"
    return "%(height)sp"


def _build_options(quality: str) -> dict:
    """
    Build the yt-dlp settings SHARED by both single-video and playlist downloads.

    The caller adds its own "outtmpl" (output path) afterwards, because that path
    is the ONE thing that differs between a single video and a playlist.
    """
    options = {
        # FIX INTERMITTENT "403 Forbidden".
        # YouTube scrambles its media URLs with a JavaScript puzzle (the "n challenge").
        # Deno is the ENGINE that runs the solver; the solver SCRIPT ships in the
        # official yt-dlp-ejs project. "ejs:github" fetches it once, then caches it.
        "remote_components": ["ejs:github"],
    }

    if quality == "audio":
        # AUDIO-ONLY: grab the best audio stream, then FFmpeg converts it to MP3.
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",  # 192 kbps = good-quality MP3
            }
        ]
    else:
        # VIDEO: translate a friendly quality name into a yt-dlp "format string".
        #   bestvideo[height<=1080]  -> best VIDEO-only stream capped at that height
        #   +bestaudio               -> MERGE with best AUDIO-only stream (needs FFmpeg)
        #   /best[height<=1080]/best -> fallbacks if separate streams don't exist
        format_map = {
            "best": "bestvideo+bestaudio/best",
            "2160": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",  # 4K
            "1440": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",  # 2K
            "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "720":  "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "480":  "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "360":  "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        }
        options["format"] = format_map.get(quality, format_map["best"])
        options["merge_output_format"] = "mp4"  # force merged output to .mp4

    return options


def _download_with_retries(url: str, options: dict) -> None:
    """
    Run a yt-dlp download, RETRYING on transient network/YouTube failures.

    Lives in ONE place so both download_video and download_playlist share it.
    """
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            # download() takes a LIST of URLs, so we wrap our single url in [ ].
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
            return  # SUCCESS — stop retrying.

        except yt_dlp.utils.DownloadError:
            # Only retry DownloadError (a network/YouTube problem worth retrying).
            # A bug in our own code should crash loudly, not be retried 3 times.
            if attempt == max_attempts:
                raise  # out of attempts — re-raise so main.py can report it

            wait_seconds = attempt * 3  # BACKOFF: wait longer each time (3s, 6s)
            print(f"  Attempt {attempt} of {max_attempts} failed — retrying in {wait_seconds}s...")
            time.sleep(wait_seconds)


def download_video(
    url: str,
    output_dir: str = "downloads",
    quality: str = "best",
) -> None:
    """
    Download a SINGLE YouTube video.

    Parameters
    ----------
    url : str
        The YouTube video URL to download.
    output_dir : str
        Folder to save into (default "downloads"). Created automatically.
    quality : str
        "best", "2160", "1440", "1080", "720", "480", "360", or "audio" (MP3).
    """
    options = _build_options(quality)

    # Save flat inside output_dir, e.g.  downloads/Video Title - 1080p.mp4
    options["outtmpl"] = f"{output_dir}/%(title)s - {_quality_label(quality)}.%(ext)s"

    # If this URL belongs to a playlist (watch?v=...&list=...), grab ONLY the single
    # video, not the whole list — downloading the list is the playlist command's job.
    options["noplaylist"] = True

    _download_with_retries(url, options)


def download_playlist(
    url: str,
    output_dir: str = "downloads",
    quality: str = "best",
) -> None:
    """
    Download an ENTIRE YouTube playlist.

    The parameters are IDENTICAL to download_video(). The only difference is the
    output path: every video lands in a subfolder named after the playlist and is
    numbered in order, so the folder stays tidy.
    """
    options = _build_options(quality)

    # Organize neatly:  downloads/<Playlist Name>/01 - <Video Title> - 1080p.mp4
    #   %(playlist_title)s    -> the playlist's name (becomes its own subfolder)
    #   %(playlist_index)02d  -> the video's position, zero-padded (01, 02, ... 10)
    options["outtmpl"] = (
        f"{output_dir}/%(playlist_title)s/"
        f"%(playlist_index)02d - %(title)s - {_quality_label(quality)}.%(ext)s"
    )

    # NOTE: we deliberately do NOT set noplaylist here, so yt-dlp downloads
    # EVERY video in the list.
    _download_with_retries(url, options)
