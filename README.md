# YT Downloader

Download YouTube videos, audio, and playlists — with **two ways to use it**:

- 🖥️ **Web UI** — a simple page in your browser (great for everyone)
- ⌨️ **Command line** — fast one-liners in the terminal (great for power users)

Both share the same download engine ([yt-dlp](https://github.com/yt-dlp/yt-dlp)) under the hood.

---

## Prerequisites

Install these once, and make sure they work from your terminal:

| Tool | Why it's needed | Download |
|------|----------------|----------|
| Python 3.10+ | Runs the tool | https://python.org |
| FFmpeg | Merges video + audio (needed for 1080p and above) | https://ffmpeg.org |
| Deno | Solves YouTube's JavaScript challenge (avoids 403 errors on high-res) | https://deno.com |

Verify:
```bash
python --version
ffmpeg -version
deno --version
```

---

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/vishalsbl123/yt-downloader.git
cd yt-downloader

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Option 1 — Web UI (easiest)

Start the app:
```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

1. Paste a YouTube URL
2. Pick a **quality** and choose **Single Video** or **Playlist**
3. Click **Download**

The file downloads straight to your browser's Downloads folder. Playlists arrive as a single `.zip`.

> While a download runs, the button shows "Downloading…". Large videos and playlists can take a while — that's normal.

---

## Option 2 — Command Line

All commands follow this pattern:
```
python main.py <command> <url> [options]
```

### Show video info (no download)
```bash
python main.py info "https://www.youtube.com/watch?v=VIDEO_ID"
```
Displays title, channel, duration, views, and upload date.

### Download a video
```bash
python main.py download "https://www.youtube.com/watch?v=VIDEO_ID"

# Specific quality
python main.py download "URL" --quality 1080

# Audio only (saves as MP3)
python main.py download "URL" --quality audio

# Save to a custom folder
python main.py download "URL" --output my-videos
```

### Download a playlist
```bash
python main.py playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

Videos are saved in a subfolder named after the playlist, numbered in order:
```
downloads/
  Playlist Name/
    01 - First Video - 720p.mp4
    02 - Second Video - 720p.mp4
    ...
```

---

## Quality Options

Used by both the Web UI and the `--quality` / `-q` flag on the command line:

| Value | Result |
|-------|--------|
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
├── app.py                     # Web UI  (Flask) — presentation layer
├── main.py                    # CLI     (argparse) — presentation layer
├── templates/
│   └── index.html             # The web page shown in the browser
├── requirements.txt           # Python dependencies
├── yt_downloader/
│   ├── __init__.py            # Marks the folder as a Python package
│   └── integrations.py        # Integration layer — the ONLY file that talks to yt-dlp
└── downloads/                 # CLI saves videos here (not tracked by git)
```

**How it's organized:** `app.py` and `main.py` are just two different "front doors."
Both call the same functions in `integrations.py`, which is the single place that
talks to YouTube. Change how downloads work in one file, and both front doors get it.

---

## Dependencies

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — downloads from YouTube
- [Flask](https://flask.palletsprojects.com/) — powers the web UI
