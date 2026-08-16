from flask import Flask, render_template, request, flash, redirect, url_for
from yt_downloader.integrations import download_video, download_playlist

app = Flask(__name__)
app.secret_key = "ytdl-secret"   # needed for flash messages


def is_valid_youtube_url(url: str) -> bool:
    return url.startswith("https://www.youtube.com/") or url.startswith("https://youtu.be/")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def handle_download():
    url     = request.form["url"]
    quality = request.form["quality"]
    kind    = request.form["kind"]      # "video" or "playlist"

    if not is_valid_youtube_url(url):
        flash("Invalid YouTube URL.", "error")
        return redirect(url_for("index"))

    try:
        if kind == "playlist":
            print("Playlist downloading started:")
            download_playlist(url, quality=quality)
            print("Playlist downloaded successfully.")
        else:
            print("Video downloading started:")
            download_video(url, quality=quality)
            print("Video downloaded successfully.")

        flash(f"Downloaded successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
