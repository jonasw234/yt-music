#!/usr/bin/env python3
"""Download music videos from YouTube and process them by stripping silence, normalizing
loudness, setting tags, and moving to a directory."""
import logging
import os
import re
import shutil
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
    Normalize filename by replacing certain characters and removing unnecessary information.

    Parameters
    ----------
    filename : str
        The name of the file to be normalized.
    uploader : str, optional
        The name of the uploader, by default ""

    Returns
    -------
    str
        The normalized filename.
    """
    logging.info("Normalizing filename.")
    new_filename = os.path.basename(filename).lower()
    # Order matters: Some replacements build on top of others!
    replace_chars = {
        "｜": "_",
        "|": "_",
        "/": "",
        '"': "",
        "＂": "",
        "  ": " ",
        "⧸": "/",
        " (lyric video)": "",
        " (lyrics)": "",
        " (official animated video)": "",
        " (official lyric video)": "",
        " (official lyrics video)": "",
        " (official music video)": "",
        " (official video)": "",
        " [official video]": "",
        " – official video clip": "",
        " (official)": "",
        " (audio)": "",
        " // official music video": "",
        " // official lyric video": "",
        f" // {uploader}": "",
        " (offizielles video)": "",
        " (official audio)": "",
        " (hq)": "",
        " (official visualizer)": "",
        " (music video)": "",
        " official video": "",
        f" ({datetime.now().year})": "",
        " ft. ": " feat. ",
        " ft.": " feat.",
        f"_ {uploader}": "",
        "_ official audio video": "",
        "_ official lyric video": "",
        "_ official music video": "",
        "'": "’",
    }

    for char, repl in replace_chars.items():
        new_filename = new_filename.replace(char, repl)

    # Titlecase can’t handle cases like `hammerfall – hammer of the dawn.mp3` (converts
    # it to `Hammerfall – Hammer of the dawn.mp3`)
    # Removing the extension fixes this
    new_filename = f"{titlecase(os.path.splitext(new_filename)[0])}.mp3"

    logging.debug("New filename: %s", new_filename)
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
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
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
                # If we found the right row, extract the genre(s) and return the first one
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

    artist, title = "", ""
    try:
        artist, title = new_filename.split(" - ", 1)
        title = title.replace(".mp3", "")
    except ValueError:
        # Sometimes artists have their own channel and publish songs only with the title
        title = new_filename.replace(".mp3", "")
        uploader = titlecase(info_dict["uploader"])
        if uploader:
            artist = uploader

    # Trim silence at beginning and end, normalize to 95 dB
    edit_audio(filename)

    # Set tags (artist, title, date)
    year = info_dict["upload_date"][:4]
    logging.warning("Using upload date as publication date: %s", year)
    if not album:
        pattern = r'album "(.+?)"'
        match = re.search(pattern, info_dict["description"], re.IGNORECASE)
        if match:
            album = match.group(1)
            logging.warning("Extracted album from description: %s", album)
    set_tags(filename, artist, title, year, album, genre)

    # Move file to appropriate directory
    move_file(filename, artist, title)


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

    # Normalize loudness
    logging.info("Normalizing loudness.")
    target_dbfs = -95
    change_in_dbfs = target_dbfs - sound.dBFS
    normalized_sound = sound.apply_gain(change_in_dbfs)
    normalized_sound.export(audio_file, format="mp3")


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
