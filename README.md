# yt-music
Downloads music from YouTube channels. Set download folder with `EXPORT YT_MUSIC_DIR="DESTINATION"`.
Needs `[yt-dlp](https://github.com/yt-dlp/yt-dlp)`, `[titlecase](https://github.com/wezm/titlecase)`, `[mp3splt](https://github.com/mp3splt/mp3splt)`, `[eyeD3](https://github.com/nicfit/eyeD3)`, and `[jq](https://github.com/stedolan/jq)`.

Usage: `yt-music.sh https://www.youtube.com/watch?v=aDaoQk081IY [ALBUM] [GENRE]`

It tries to download the file (skipping parts marked by SponsorBlock API), set correct metadata, remove suffixes from the title (e.g. “(OFFICIAL AUDIO VIDEO)” etc.), trims silence from the beginning and end, normalizes loudness to 95 dB, and finally moves the file to the destination folder.

Should be seen as an inspiration and adopted for your needs/favorite music channels.
