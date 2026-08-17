# YT Downloader — Technical Documentation

This document explains **how the tool is built and why**, file by file and concept
by concept. If the [README](README.md) tells you how to *use* the tool, this tells
you how it *works* — enough that a new developer could confidently change it.

---

## Table of Contents

1. [The Big Idea: Layered Architecture](#1-the-big-idea-layered-architecture)
2. [How a Request Flows Through the Code](#2-how-a-request-flows-through-the-code)
3. [The Environment: Python, FFmpeg, Deno](#3-the-environment-python-ffmpeg-deno)
4. [File-by-File Walkthrough](#4-file-by-file-walkthrough)
   - [integrations.py — the engine](#integrationspy--the-engine)
   - [main.py — the CLI](#mainpy--the-cli)
   - [app.py — the web UI](#apppy--the-web-ui)
   - [templates/index.html — the web page](#templatesindexhtml--the-web-page)
5. [Design Decisions & Trade-offs](#5-design-decisions--trade-offs)
6. [The Tricky Bits, Explained](#6-the-tricky-bits-explained)
7. [Glossary](#7-glossary)

---

## 1. The Big Idea: Layered Architecture

The whole project is organized around one principle: **separation of concerns**.
Each file has exactly one job, and the jobs are stacked in layers.

```
        ┌─────────────────────┐     ┌─────────────────────┐
        │   main.py  (CLI)    │     │   app.py  (Web UI)  │   ← Presentation layer
        │   argparse          │     │   Flask + HTML      │     "front doors"
        └──────────┬──────────┘     └──────────┬──────────┘
                   │                            │
                   └────────────┬───────────────┘
                                ▼
                 ┌───────────────────────────────┐
                 │  yt_downloader/integrations.py │            ← Integration layer
                 │  the ONLY file that uses yt-dlp│              "the engine"
                 └───────────────┬───────────────┘
                                 ▼
                          ┌──────────────┐
                          │    yt-dlp    │                     ← External library
                          │  → YouTube   │
                          └──────────────┘
```

**Why this matters:**

- **One place to change YouTube logic.** If YouTube changes or we swap yt-dlp for
  another library, only `integrations.py` changes. The CLI and web UI don't care.
- **Two front doors, one engine.** The CLI and the web UI are just different ways
  to *ask* for a download. They both call the same three functions. No logic is
  duplicated between them.
- **Each file is easy to reason about.** `main.py` only knows about the terminal.
  `app.py` only knows about the browser. `integrations.py` only knows about yt-dlp.

This is the **Single Responsibility Principle**: a module should have one reason to change.

---

## 2. How a Request Flows Through the Code

Same engine, two entry points. Here is the exact path for each.

**Command line** — `python main.py download "URL" -q 720`
```
Terminal
  → main.py: argparse parses "download", url, quality
  → main.py: cmd_download() validates the URL, prints status
  → integrations.py: download_video(url, output_dir, quality)
  → integrations.py: _build_options() + _download_with_retries()
  → yt-dlp → YouTube → file saved to downloads/
```

**Web UI** — clicking **Download** in the browser
```
Browser form (index.html)
  → HTTP POST to /download
  → app.py: handle_download() validates the URL
  → integrations.py: download_video(url, output_dir=<temp folder>, quality)
  → yt-dlp → YouTube → file saved to a TEMP folder
  → app.py: send_file() streams that file back to the browser
  → browser saves it to the user's Downloads folder
  → app.py: @after_this_request deletes the temp folder
```

The only real difference: the CLI leaves the file on disk in `downloads/`; the web
UI puts it in a throwaway temp folder, ships it to the browser, then cleans up.

---

## 3. The Environment: Python, FFmpeg, Deno

Three programs must be installed on the machine. Here is *why each one exists*.

| Tool | Role | What breaks without it |
|------|------|------------------------|
| **Python 3.10+** | Runs all our code | Nothing runs at all. (We use `str \| None` syntax, which needs 3.10+.) |
| **FFmpeg** | Merges separate video + audio streams into one file; converts audio to MP3 | 1080p+ downloads fail (YouTube serves HD video and audio as *separate* streams that must be merged); `--quality audio` can't make an MP3 |
| **Deno** | A JavaScript runtime that solves YouTube's "n challenge" (see [§6](#6-the-tricky-bits-explained)) | Intermittent `403 Forbidden` on high-resolution streams |

Python packages (installed into a `.venv` via `pip install -r requirements.txt`):

- **yt-dlp** — the library that actually talks to YouTube.
- **Flask** — the web framework that powers `app.py`.

Everything runs inside a **virtual environment** (`.venv`) so this project's
packages stay isolated from other Python projects on the machine.

---

## 4. File-by-File Walkthrough

```
yt-downloader/
├── app.py                     # Web UI (Flask)
├── main.py                    # CLI (argparse)
├── templates/index.html       # The web page
├── requirements.txt           # Python dependencies
├── yt_downloader/
│   ├── __init__.py            # Marks the folder as an importable package
│   └── integrations.py        # THE ENGINE — only file that talks to yt-dlp
└── downloads/                 # CLI output (ignored by git)
```

### integrations.py — the engine

The only file that imports `yt_dlp`. Six functions; three are public (called by the
front doors) and three are private helpers (prefixed with `_`, a Python convention
meaning "internal — don't call me from outside this file").

**`fetch_video_info(url) -> dict`** — metadata only, no download.
```python
options = {"quiet": True, "no_warnings": True, "skip_download": True}
with yt_dlp.YoutubeDL(options) as ydl:
    info = ydl.extract_info(url, download=False)
return info
```
`skip_download` + `download=False` mean we ask YouTube "tell me about this video"
without pulling the video itself. Returns a dict (`title`, `uploader`, `duration`,
`view_count`, `upload_date`, …) that `cmd_info` formats for display.

**`_quality_label(quality) -> str`** — the text stamped into the filename.
Returns the literal `"audio"` for audio, otherwise `"%(height)sp"` — a yt-dlp
*placeholder* that becomes the real resolution at download time (e.g. `1080p`).

**`_build_options(quality) -> dict`** — the yt-dlp settings shared by every download.
This is where DRY lives: both `download_video` and `download_playlist` call it, so
the format logic exists once. It:
- always sets `"remote_components": ["ejs:github"]` (the 403 fix),
- for `audio`, requests the best audio stream + an FFmpeg MP3 post-processor,
- otherwise maps a friendly quality (`"1080"`) to a yt-dlp **format string**
  (`bestvideo[height<=1080]+bestaudio/best[height<=1080]/best`) and forces the
  merged result to `.mp4`.

A yt-dlp format string reads like this:
```
bestvideo[height<=1080] + bestaudio / best[height<=1080] / best
└── best video ≤1080p ──┘ └─ merged ┘ └──────── fallbacks if no separate streams ─────┘
```

**`_download_with_retries(url, options) -> None`** — resilience in one place.
```python
for attempt in range(1, max_attempts + 1):
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
        return                       # success → stop
    except yt_dlp.utils.DownloadError:
        if attempt == max_attempts:
            raise                    # out of tries → let the caller report it
        time.sleep(attempt * 3)      # backoff: 3s, then 6s
```
Note it catches **only** `DownloadError` — a network/YouTube problem worth retrying.
A bug in *our* code raises a different exception and is allowed to crash loudly
instead of being silently retried three times.

**`download_video(url, output_dir, quality)`** and
**`download_playlist(url, output_dir, quality)`** — the two public download
functions. They are almost identical; the *only* real difference is the output path
(`outtmpl`):
- video → `downloads/Title - 1080p.mp4`, and sets `noplaylist=True` so a
  `watch?v=...&list=...` URL grabs just the one video;
- playlist → `downloads/<Playlist Name>/01 - Title - 1080p.mp4`, numbered and
  foldered, and deliberately does *not* set `noplaylist`, so the whole list downloads.

### main.py — the CLI

Turns terminal arguments into calls on the engine, using Python's built-in
`argparse`. Three subcommands: `info`, `download`, `playlist`.

**The DRY trick — a "parent parser".** `download` and `playlist` take the exact
same options (`url`, `--quality`, `--output`). Rather than declare them twice, they
are declared once on a parent parser and *inherited*:
```python
common = argparse.ArgumentParser(add_help=False)   # add_help=False avoids a clash
common.add_argument("url", ...)
common.add_argument("--quality", "-q", ...)
common.add_argument("--output", "-o", ...)

subparsers.add_parser("download", parents=[common], ...)
subparsers.add_parser("playlist", parents=[common], ...)
```

**The dispatch pattern — no if/elif chain.** Each subparser records which handler
to call via `set_defaults(func=...)`, and `main()` just calls it:
```python
info_parser.set_defaults(func=cmd_info)
download_parser.set_defaults(func=cmd_download)
playlist_parser.set_defaults(func=cmd_playlist)
...
args = parser.parse_args()
args.func(args)          # calls the right cmd_* function automatically
```

**Guard clauses.** Each handler validates the URL first and bails out early with a
clear message, using a shared helper so the rule lives in one place:
```python
def is_valid_youtube_url(url: str) -> bool:
    return url.startswith("https://www.youtube.com/") or url.startswith("https://youtu.be/")
```

### app.py — the web UI

A small Flask app: two routes (`/` shows the page, `/download` handles the form).
It reuses the same URL-validation idea and calls the same engine functions.

The interesting part is getting the finished file *back to the browser*:
```python
work_dir = tempfile.mkdtemp()                  # a fresh empty folder per request
download_video(url, output_dir=work_dir, quality=quality)
filename  = os.listdir(work_dir)[0]            # whatever appeared IS the result
send_path = os.path.join(work_dir, filename)

@after_this_request                            # runs AFTER the file finishes sending
def cleanup(response):
    shutil.rmtree(work_dir, ignore_errors=True)
    return response

response = send_file(send_path, as_attachment=True, download_name=filename)
response.set_cookie("fileDownloadToken", token, path="/")   # tells the browser we're done
return response
```
Playlists produce many files, but a browser can only receive one file per request,
so the playlist folder is zipped with `shutil.make_archive` and sent as `playlist.zip`.

### templates/index.html — the web page

Plain HTML + CSS + a little JavaScript. Three things worth knowing:

- **Jinja2 templating.** Flask fills the page in before sending it. `{{ ... }}`
  prints a value; `{% ... %}` is logic (a loop); `{# ... #}` is a template comment.
  The flash-message block uses a loop:
  ```html
  {% for category, message in get_flashed_messages(with_categories=True) %}
      <div class="message {{ category }}">{{ message }}</div>
  {% endfor %}
  ```
  > Gotcha: Jinja2 processes `{{ }}` / `{% %}` **even inside HTML `<!-- -->`
  > comments**. Use `{# #}` for comments in templates.

- **The loading state.** On submit, JavaScript disables the button and shows
  "Downloading…" so the page doesn't look frozen.

- **Knowing when the download finished.** A file download doesn't reload the page,
  so JavaScript can't normally tell it's done. The trick: the form sends a random
  `token`; the server echoes it back as a `fileDownloadToken` cookie on the
  `send_file` response; the page polls for that cookie and, when it appears, resets
  the button. (This is the well-known "jQuery File Download" cookie technique.)

---

## 5. Design Decisions & Trade-offs

| Decision | Why | Trade-off accepted |
|----------|-----|--------------------|
| Isolate all yt-dlp use in `integrations.py` | One place to change if YouTube/yt-dlp changes | A little extra indirection |
| Two front doors (CLI + web) sharing one engine | No duplicated download logic | Two presentation files to maintain |
| Parent parser + dispatch in the CLI | DRY; no if/elif chain | Slightly less obvious to a beginner |
| Retry only on `DownloadError` | Real bugs crash loudly instead of retrying 3× | Some transient non-DownloadError blips aren't retried |
| Inline date formatting in `cmd_info` | It's a one-line, single-use transform (YAGNI) | Not reusable — fine, nothing else needs it |
| Web UI downloads to a temp folder + `send_file` | Behaves like a real web app; browser gets the file | Extra temp-file bookkeeping and cleanup |
| Removed cookies & subtitles features | Cookies = fragile (Chrome locks/encrypts its DB); subtitles = HTTP 429 rate-limits | Fewer features, but far fewer failures |
| Local-only, not deployed | YouTube blocks datacenter IPs; many hosts ban downloaders | Not reachable 24/7 from anywhere |

**YAGNI ("You Aren't Gonna Need It")** and **DRY ("Don't Repeat Yourself")** were
the two rules of thumb applied throughout: don't add structure until complexity
demands it, but never copy-paste the same logic twice.

---

## 6. The Tricky Bits, Explained

**The "n challenge" and the 403 fix.** YouTube protects its media URLs with a
JavaScript puzzle (nicknamed the *n challenge*). yt-dlp must solve it to get a
working download URL, and solving it requires (a) a JavaScript engine and (b) the
solver script:
- **Deno** is the engine that *runs* the solver.
- `"remote_components": ["ejs:github"]` tells yt-dlp to fetch the solver script from
  the official `yt-dlp-ejs` GitHub project (once, then cached).

With both present, intermittent `403 Forbidden` errors on high-resolution streams go
away. This single option lives in `_build_options`, so every download benefits.

**Why HD needs FFmpeg.** For anything above 720p, YouTube serves the video track and
the audio track as *separate* streams. yt-dlp downloads both, then FFmpeg merges them
into one `.mp4`. No FFmpeg → no merge → HD fails. The same tool converts audio-only
downloads into MP3.

**Finding the downloaded filename (web UI).** We can't predict the final filename
because yt-dlp builds it from a template (`%(title)s`) and post-processing changes
the extension. The robust trick: download into a **brand-new empty temp folder**,
then whatever single file is in it afterwards *is* the result — no guessing.

**Deleting temp files at the right time.** `send_file` *streams* the file to the
browser; deleting it too early would break the download mid-transfer.
`@after_this_request` registers cleanup to run **after** the response is fully sent,
so the file survives exactly as long as it's needed.

**Features we deliberately removed.**
- *Cookies* (for age-restricted/private videos): reading a browser's cookie store is
  fragile — the browser locks the database while open, and modern Chrome encrypts it
  with Windows DPAPI in a way yt-dlp couldn't decrypt. Removed.
- *Subtitles*: downloading subtitle tracks triggered YouTube `HTTP 429 Too Many
  Requests` rate-limiting, which then cascaded into failed video downloads. Removed.

---

## 7. Glossary

- **Layered / N-tier architecture** — organizing code into stacked layers
  (presentation → integration → external), each depending only on the one below.
- **Separation of concerns / Single Responsibility Principle** — each module has one
  job and one reason to change.
- **DRY (Don't Repeat Yourself)** — define each piece of logic once.
- **YAGNI (You Aren't Gonna Need It)** — don't add structure before it's needed.
- **Guard clause** — validate inputs at the top of a function and return early on
  bad input, instead of nesting the whole body in an `if`.
- **Dispatch pattern** — map each command to its handler function and call it
  directly, avoiding a long `if/elif` chain.
- **Parent parser** — an argparse parser whose arguments are inherited by several
  subcommands, so shared options are declared once.
- **Format string (yt-dlp)** — a mini-expression telling yt-dlp which video/audio
  streams to pick and how to fall back.
- **Output template (yt-dlp)** — a filename pattern with placeholders like
  `%(title)s`, `%(ext)s`, `%(playlist_index)02d`, filled in at download time.
- **Post-processor (yt-dlp)** — a step run after download, e.g. extracting audio to
  MP3 or merging streams (both via FFmpeg).
- **n challenge** — YouTube's JavaScript puzzle that scrambles media URLs; solved by
  Deno + the EJS solver script.
- **Virtual environment (`.venv`)** — an isolated per-project set of Python packages.
- **Route (Flask)** — a URL path bound to a Python function.
- **Jinja2** — Flask's templating language: `{{ value }}`, `{% logic %}`,
  `{# comment #}`.
- **`send_file` (Flask)** — streams a file to the browser as a download.
- **`@after_this_request` (Flask)** — runs a function after the response is sent
  (used here to delete temp files safely).
```
