"""
main.py  —  THE ENTRY POINT (Presentation Layer)
=================================================
This is the file you RUN. Its only jobs are:
    1. Parse what you typed on the command line (argparse).
    2. Call the right function from the integration layer.
    3. Print results clearly.

It knows NOTHING about how yt-dlp works internally.
"""

import sys
import argparse
from yt_downloader.integrations import fetch_video_info, download_video, download_playlist


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def format_duration(seconds: int) -> str:
    """Convert raw seconds into a human-readable string like '3:33' or '1:04:09'."""
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# ---------------------------------------------------------------------------
# SUBCOMMAND HANDLERS
# One function per subcommand. argparse calls the right one automatically.
# Each receives 'args' — an object whose attributes are whatever the user typed.
# ---------------------------------------------------------------------------

def cmd_info(args):
    """Handler for:  python main.py info <url>"""
    print(f"\nFetching info for: {args.url}\n")

    info = fetch_video_info(args.url)

    title       = info.get("title", "Unknown")
    uploader    = info.get("uploader", "Unknown")
    duration    = info.get("duration", 0)
    views       = info.get("view_count", 0)
    upload_date = info.get("upload_date", "")

    # inline date formatting: "20050424" -> "2005-04-24"
    if len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    else:
        upload_date = "Unknown"

    print("=" * 45)
    print(f"  Title    : {title}")
    print(f"  Channel  : {uploader}")
    print(f"  Duration : {format_duration(duration)}")
    print(f"  Views    : {views:,}")
    print(f"  Uploaded : {upload_date}")
    print("=" * 45 + "\n")


def cmd_download(args):
    """
    Handler for the 'download'
    subcommand: download a video via the integration layer.
    """

    print("Downloading started:")
    download_video(args.url, args.output, args.quality)
    print("Download finished successfully...")


def cmd_playlist(args):
    """Handler for:  python main.py playlist <url> [options]"""
    print("Playlist downloading started:")
    download_playlist(args.url, args.output, args.quality)
    print("Playlist downloaded successfully.")


# ---------------------------------------------------------------------------
# CLI SETUP — build the argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """
    Construct and return the full CLI parser.
    Kept in its own function so main() stays clean and readable.
    """

    # The top-level parser. 'description' appears in --help output.
    parser = argparse.ArgumentParser(
        prog="ytdl",
        description="YT Downloader — download YouTube videos and playlists.",
    )

    # add_subparsers() creates a "sub-menu". dest="command" records which
    # subcommand was typed; required=True forces the user to pick one.
    subparsers = parser.add_subparsers(dest="command", required=True)


    # --- SUBCOMMAND: info ---------------------------------------------------
    info_parser = subparsers.add_parser(
        "info",
        help="Show video metadata without downloading.",
    )
    info_parser.add_argument("url", help="The YouTube video URL.")
    info_parser.set_defaults(func=cmd_info)


    # --- SHARED ARGUMENTS (a "parent" parser) -------------------------------
    # 'download' and 'playlist' take the EXACT same options. Rather than write
    # them twice (duplication!), we define them ONCE on a parent parser, then
    # let both subcommands INHERIT them via parents=[common]. This is the DRY
    # principle applied to the CLI — the same lesson as the integrations refactor.
    #
    # add_help=False is REQUIRED: without it, this parent AND the real subcommand
    # would each try to add a -h/--help option, and argparse would error on the clash.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "url",
        help="The YouTube URL (a video for 'download', a playlist for 'playlist').",
    )
    common.add_argument(
        "--quality", "-q",
        default="best",
        choices=["best", "2160", "1440", "1080", "720", "480", "360", "audio"],
        help="Quality (default: best).",
    )
    common.add_argument(
        "--output", "-o",
        default="downloads",
        help="Folder to save into (default: downloads/).",
    )


    # --- SUBCOMMAND: download (inherits the shared args) --------------------
    download_parser = subparsers.add_parser(
        "download",
        parents=[common],                       # <-- inherit all six shared args
        help="Download a single YouTube video.",
    )
    download_parser.set_defaults(func=cmd_download)


    # --- SUBCOMMAND: playlist (inherits the SAME shared args) --------------
    playlist_parser = subparsers.add_parser(
        "playlist",
        parents=[common],                       # <-- same args, zero duplication
        help="Download an entire YouTube playlist.",
    )
    playlist_parser.set_defaults(func=cmd_playlist)

    return parser


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()

    # parse_args() reads what the user typed and returns a neat object.
    # Invalid input makes argparse print an error and exit by itself.
    args = parser.parse_args()

    # THE DISPATCH: call whichever handler argparse stored in args.func.
    try:
        args.func(args)
    except Exception as exc:
        print(f"\nError: {exc}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
