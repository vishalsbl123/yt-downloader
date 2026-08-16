"""
app.py  —  THE WEB PRESENTATION LAYER (Flask)
=============================================
A browser-based front end for the SAME engine the CLI uses.

Like main.py, this file only:
    1. Reads what the user submitted in the web form.
    2. Calls the integration layer (yt_downloader/integrations.py).
    3. Sends the finished file back to the user's browser.

It knows NOTHING about how yt-dlp works — that lives in integrations.py.
"""

import os
import shutil
import tempfile

from flask import (
    Flask, render_template, request, flash, redirect, url_for,
    send_file, after_this_request,
)
from yt_downloader.integrations import download_video, download_playlist

app = Flask(__name__)
app.secret_key = "ytdl-secret"   # needed for flash messages


def is_valid_youtube_url(url: str) -> bool:
    """Return True if url is a recognisable YouTube link (full or short)."""
    return url.startswith("https://www.youtube.com/") or url.startswith("https://youtu.be/")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def handle_download():
    url     = request.form["url"]
    quality = request.form["quality"]
    kind    = request.form["kind"]              # "video" or "playlist"
    token   = request.form.get("download_token", "")  # used by the browser to detect completion

    if not is_valid_youtube_url(url):
        flash("Invalid YouTube URL.", "error")
        return redirect(url_for("index"))

    # Each request downloads into its OWN fresh temp folder. That way we can look
    # inside afterwards and know EXACTLY which file(s) this request produced,
    # without clashing with any other download happening at the same time.
    work_dir = tempfile.mkdtemp()
    temp_dirs = [work_dir]   # everything we must delete once the response is sent

    try:
        if kind == "playlist":
            download_playlist(url, output_dir=work_dir, quality=quality)
            # A playlist is MANY files — a browser can only receive ONE file per
            # request, so we bundle the whole folder into a single .zip.
            zip_dir = tempfile.mkdtemp()
            temp_dirs.append(zip_dir)
            send_path = shutil.make_archive(os.path.join(zip_dir, "playlist"), "zip", work_dir)
            download_name = "playlist.zip"
        else:
            download_video(url, output_dir=work_dir, quality=quality)
            # A single video leaves exactly ONE finished file in work_dir.
            filename = os.listdir(work_dir)[0]
            send_path = os.path.join(work_dir, filename)
            download_name = filename
    except Exception as exc:
        # Download failed — clean up and show the error on the page.
        for directory in temp_dirs:
            shutil.rmtree(directory, ignore_errors=True)
        flash(f"Error: {exc}", "error")
        return redirect(url_for("index"))

    # send_file STREAMS the file to the browser. We must NOT delete it before that
    # finishes, so we register the cleanup to run AFTER the response has been sent.
    @after_this_request
    def cleanup(response):
        for directory in temp_dirs:
            shutil.rmtree(directory, ignore_errors=True)
        return response

    response = send_file(send_path, as_attachment=True, download_name=download_name)
    # Echo the token back as a cookie. The browser's JavaScript watches for this
    # cookie to know the download has started, so it can reset the button.
    response.set_cookie("fileDownloadToken", token, path="/")
    return response


if __name__ == "__main__":
    app.run(debug=True)
