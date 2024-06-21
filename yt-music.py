#!/usr/bin/env python3
"""Download music videos from YouTube and process them by stripping silence, normalizing
loudness, setting tags, and moving to a directory."""
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

import eyed3
import wikipedia
from bs4 import BeautifulSoup
from pydub import AudioSegment
from titlecase import titlecase
from yt_dlp import YoutubeDL

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
DESTINATION = "Q:\\"


def normalize_filename(filename: str, uploader: str = "") -> str:
    """
    Normalize filename by replacing certain characters and removing unnecessary
    information.

    Parameters
    ----------
    filename : str
        The name of the file to be normalized.
    uploader : str, optional
        The name of the uploader, by default ""

    Returns
    -------
    str
        The normalized filename in the form `Artist - Title`.
    """
    logging.info("Normalizing filename.")
    new_filename = os.path.basename(filename).lower()

    # Order matters for groups: Some replacements build on top of others!
    replace_chars = {
        # Needs to come first, difficult to remove later
        f" // {uploader}": "",
        # Replacements of common annoyances
        "'": "’",
        "/": "",
        "|": "",
        "–": "",
        "⧸": "",
        "＂": "",
        "｜": "",
        '"': "",
        # Mostly suffixes in video titles
        " (audio)": "",
        " (hq)": "",
        " (lyric video)": "",
        " (lyrics)": "",
        " (music video)": "",
        " (official animated video)": "",
        " (official audio)": "",
        " (official lyric video)": "",
        " (official lyrics video)": "",
        " (official music video)": "",
        " (official video)": "",
        " (official visualizer)": "",
        " (official)": "",
        " (offizielles video)": "",
        " (performance video)": "",
        " [official video]": "",
        " official audio video": "",
        " official lyric video": "",
        " official music video": "",
        " official video clip": "",
        " official video": "",
        " – official video clip": "",
        f" ({datetime.now().year})": "",
        f"_ {uploader.lower()}": "",
        f" {uploader.lower()}": "",
        # Normalize “featuring”
        " ft. ": " feat. ",
        " ft.": " feat.",
        # Needs to come last, might be necessary after previous replacements
        "  ": " ",
    }
    for char, repl in replace_chars.items():
        new_filename = new_filename.replace(char, repl)

    # Sometimes artists name their videos: `Artist: "Title"`
    parts = new_filename.split("： ")
    if len(parts) >= 2 and parts[0] in uploader.lower():
        new_filename = new_filename.replace("： ", " - ", 1)

    # Temporarily remove extension (hinders some later operations)
    new_filename, extension = os.path.splitext(new_filename)
    new_filename = new_filename.strip()

    # Move “feat.” to the end of the title
    feat_parts = new_filename.split(" feat. ")
    if len(feat_parts) > 1 and " - " in feat_parts[1]:
        new_filename = (
            f"{feat_parts[0]} - {feat_parts[1].split(' - ')[1]} feat. "
            f"{feat_parts[1].split(' - ')[0]}"
        )

    # Titlecase for the filename
    new_filename = f"{titlecase(new_filename)}{extension}"
    # feat. should be lowercase
    new_filename = new_filename.replace(" Feat. ", " feat. ")

    logging.info("New filename: %s", new_filename)
    return new_filename


def download_audio(url: str) -> Tuple[str, dict[str, str]]:
    """
    Download the audio file from YouTube and return its path.

    Parameters
    ----------
    url : str
        The URL of the YouTube video to download.

    Returns
    -------
    str
        The path to the downloaded audio file.
    """
    logging.info("Downloading audio file.")
    with YoutubeDL(
        {
            "windowsfilenames": True,
            "no-playlist": True,
            "embed-metadata": True,
            "write-info-json": True,
            "extract-audio": True,
            "sponsorblock-remove": "all",
            "outtmpl": "%(title)s.%(ext)s",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"},
                {"key": "SponsorBlock", "categories": ["all"]},
                {"key": "ModifyChapters", "remove_sponsor_segments": ["all"]},
            ],
        }
    ) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        ydl.download(url)
        filename = f"{os.path.splitext(ydl.prepare_filename(info_dict))[0]}.mp3"
        return filename, info_dict if info_dict else {"": ""}


def set_tags(
    filename: str, artist: str, title: str, year: str, album: str = "", genre: str = ""
):
    """
    Set artist, title, date, album, and genre tags for the audio file.

    Parameters
    ----------
    filename : str
        The path to the audio file.
    artist : str
        The name of the artist.
    title : str
        The title of the song.
    year : str
        The year the song was released.
    album : str, optional
        The name of the album, by default "".
    genre : str, optional
        The genre of the song, by default "".
    """
    logging.info("Setting tags.")
    audio_file = eyed3.load(filename)
    if not audio_file or not audio_file.tag:
        # Handle the case where the file couldn’t be loaded or has no tags
        logging.error("eyeD3 wasn’t able to load the file or find any tags.")
        sys.exit(2)
    tag = audio_file.tag

    # Fix artist casing if necessary
    artist_dir_path = str(Path(os.path.join(DESTINATION, artist)).resolve())
    if os.path.isdir(artist_dir_path):
        # If an artist directory already exists, use its name instead of the one passed
        # as a parameter
        artist = os.path.basename(artist_dir_path)
    tag.artist = artist

    # Use reference files for genre if not user supplied
    if not genre:
        genre = find_genre(artist, artist_dir_path)
    tag.genre = genre

    tag.title = title
    tag.recording_date = year
    tag.album = album

    tag.save()


def find_genre(artist: str, artist_dir_path: str = "") -> str:
    """
    Try to find the main genre for an artist.

    Parameters
    ----------
    artist : str
        The name of the artist
    artist_dir_path : str
        The directory where reference files might be found

    Returns
    -------
    str
        The genre for the artist
    """
    # First try to find reference files
    if os.path.isdir(artist_dir_path):
        artist_files = os.listdir(artist_dir_path)
        if len(artist_files) > 0:
            reference_file = eyed3.load(os.path.join(artist_dir_path, artist_files[0]))
            if not reference_file or not reference_file.tag:
                logging.error(
                    "eyeD3 wasn’t able to load the reference file or find any tags."
                )
            else:
                logging.warning(
                    "Using existing references for genre: %s", reference_file.tag.genre
                )
                return str(reference_file.tag.genre)

    # If a genre is still not found, try to find it on Wikipedia
    for lang in ["en", "de"]:
        wikipedia.set_lang(lang)
        try:
            page = wikipedia.page(artist)
        except wikipedia.exceptions.PageError:
            logging.error("Couldn’t find a %s Wikipedia page for %s", lang, artist)
            continue

        # Next, parse the HTML content of the page using BeautifulSoup
        soup = BeautifulSoup(page.html(), "html.parser")

        # Look for the infobox on the page, which contains information about the artist
        infobox = soup.find("table", {"class": "infobox"})
        if not infobox:
            logging.error(
                "Couldn’t find an infobox on the %s %s Wikipedia page", lang, artist
            )
            continue

        # Look for the row in the infobox that contains the artist’s genre
        for row in infobox.find_all("tr"):
            if row.th and (row.th.text in ("Genres", "Genre(s)")):
                # If we found the right row, extract the genre(s) and return the first
                # one
                return ";".join(
                    [titlecase(a.text).replace("-", " ") for a in row.td.find_all("a")]
                )

    logging.error(
        "Still missing genre tag (no reference files or Wikipedia information found)"
    )
    return ""


def move_file(filename: str, artist: str, title: str):
    """
    Move the audio file to the appropriate directory.

    Parameters
    ----------
    filename : str
        The path to the audio file.
    artist : str
        The name of the artist.
    title : str
        The title of the song.
    """
    artist_dir_path = str(Path(os.path.join(DESTINATION, artist)).resolve())
    os.makedirs(artist_dir_path, exist_ok=True)
    output_path = os.path.join(artist_dir_path, f"{title}.mp3")
    shutil.move(filename, output_path)
    logging.info("Moved file to %s", output_path)


def process_audio(url: str, album: str = "", genre: str = ""):
    """
    Download the audio file from YouTube, process it, set appropriate tags, and move it
    to the appropriate directory.

    Parameters
    ----------
    url : str
        The URL of the YouTube video to download.
    album : str, optional
        The name of the album, by default "".
    genre : str, optional
        The genre of the song, by default "".
    """
    # Download file
    filename, info_dict = download_audio(url)

    # Normalize filename
    new_filename = normalize_filename(filename, info_dict["uploader"])

    try:
        os.rename(filename, new_filename)
    except FileExistsError:
        # Probably an error during the previous download, so just remove the old file
        os.remove(filename)

    artist, title = "", ""
    try:
        artist, title = new_filename.split(" - ", 1)
        title = title.replace(".mp3", "")
    except ValueError:
        # Sometimes artists have their own channel and publish songs only with the title
        title = new_filename.replace(".mp3", "")
        artist = titlecase(info_dict["uploader"].replace(" - Topic", ""))

    # Trim silence at beginning and end, normalize to 95 dB
    edit_audio(new_filename)

    # Set tags (artist, title, date)
    year = info_dict["upload_date"][:4]
    logging.warning("Using upload date as publication date: %s", year)
    if not album:
        # FIXME Album cannot be extracted by yt-dlp:
        # https://github.com/onnowhere/youtube_music_playlist_downloader/issues/6
        pattern = (
            # Prefix: Album, Single, EP, or Order (case insensitive) followed by comma
            # or colon (optional) and whitespace.
            r"(?:album|Album|ALBUM|single|Single|SINGLE|ep|EP|order|Order|ORDER)[,:]?\s+"
            "(?:"  # Beginning of possible album title
            # Album title enclosed in double quotes
            '\"(.+?)\"|'
            # Album title enclosed in single quotes
            "'(.+?)'|"
            # Album title enclosed in English typographic quotes
            "“(.+?)”|"
            # Album title enclosed in German typographic quotes
            "„(.+?)“|"
            # Album title enclosed between commas (e.g. “new album, Album title, out
            # now”) or a period
            r"([^,]+?)\b|"
            # Album title all uppercase
            r"([A-Z]{2,}(?:\s+[A-Z]{2,})+)"
            ")"  # End of possible album title
        )
        match = re.search(pattern, info_dict["description"])
        if match:
            if isinstance(match, str):
                album = titlecase(match)
            else:
                album = titlecase(match.group(1))
            logging.warning("Extracted album from description: %s", album)
        else:
            logging.error(
                "Regex for album extraction failed. "
                '`info_dict["description"]` for debugging purposes: %s. Trying to '
                "extract with pattern %s.",
                info_dict["description"],
                pattern,
            )
    else:
        logging.warning("Using album supplied by user: %s", album)
    set_tags(new_filename, artist, title, year, album, genre)

    # Move file to appropriate directory
    move_file(new_filename, artist, title)


def edit_audio(audio_file: str):
    """
    Edit the audio by removing silence and normalizing loudness.

    Parameters
    ----------
    audio_file : str
        The path to the audio file to be edited.
    """
    sound = AudioSegment.from_file(audio_file, format="mp3")
    logging.info("Stripping silence from audio file.")
    sound.strip_silence()
    sound.export(audio_file, format="mp3")

    # Normalize loudness
    logging.info("Normalizing loudness of audio file.")
    subprocess.run(["mp3gain", "-r", "-p", audio_file], check=True)


def main():
    """
    Download audio file, process it, set appropriate tags, and move it to the
    appropriate directory.
    """
    # Print usage information
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        logging.error(
            "Usage: %s https://www.youtube.com/watch?v=aDaoQk081IY [ALBUM] [GENRE]",
            sys.argv[0],
        )
        sys.exit(1)

    url = sys.argv[1]
    album = sys.argv[2] if len(sys.argv) >= 3 else ""
    genre = sys.argv[3] if len(sys.argv) >= 4 else ""

    process_audio(url, album, genre)


if __name__ == "__main__":
    main()
