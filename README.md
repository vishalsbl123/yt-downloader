# YT Downloader

A personal command-line tool to download YouTube videos, audio, and playlists — built with Python and [yt-dlp](https://github.com/yt-dlp/yt-dlp).

---

## Prerequisites

Before you begin, make sure the following are installed on your machine:

| Tool | Why it's needed | Download |
|------|----------------|----------|
| Python 3.10+ | Runs the tool | https://python.org |
| FFmpeg | Merges video + audio streams (required for 1080p and above) | https://ffmpeg.org |
| Deno | Solves YouTube's JavaScript challenge (fixes 403 errors on high-res streams) | https://deno.com |

Verify they are all accessible from your terminal:
```bash
python --version
ffmpeg -version
deno --version
```

---

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/yt-downloader.git
cd yt-downloader

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Usage

All commands follow this pattern:
```
python main.py <command> <url> [options]
```

### Show video info (no download)
```bash
python main.py info "https://www.youtube.com/watch?v=VIDEO_ID"
```
Displays title, channel, duration, views, and upload date.

---

### Download a video
```bash
python main.py download "https://www.youtube.com/watch?v=VIDEO_ID"
```

With options:
```bash
# Specific quality
python main.py download "URL" --quality 1080

# Audio only (saves as MP3)
python main.py download "URL" --quality audio

# Save to a custom folder
python main.py download "URL" --output my-videos
```

---

### Download a playlist
```bash
python main.py playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

Videos are saved in a subfolder named after the playlist and numbered in order:
```
downloads/
  Playlist Name/
    01 - First Video - 720p.mp4
    02 - Second Video - 720p.mp4
    ...
```

---

## Quality Options

| Flag | Result |
|------|--------|
| `best` | Highest available quality (default) |
| `2160` | 4K |
| `1440` | 2K |
| `1080` | Full HD |
| `720` | HD |
| `480` | SD |
| `360` | Low |
| `audio` | Audio only, saved as MP3 |

```bash
python main.py download "URL" --quality 720
python main.py download "URL" -q audio
```

---

## Project Structure

```
yt-downloader/
├── main.py                    # Entry point — CLI parsing and command dispatch
├── requirements.txt           # Python dependencies
├── yt_downloader/
│   ├── __init__.py            # Marks the folder as a Python package
│   └── integrations.py        # Integration layer — the only file that talks to yt-dlp
└── downloads/                 # Videos saved here (not tracked by git)
```

---

## Dependencies

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — the engine that downloads from YouTube
