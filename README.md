# yt-music
Downloads music from YouTube channels. Set download folder with `export YT_MUSIC_PATH="DESTINATION"`.  

Needs [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), [`titlecase`](https://github.com/wezm/titlecase), [`mp3splt`](https://github.com/mp3splt/mp3splt), [`eyeD3`](https://github.com/nicfit/eyeD3), and [`jq`](https://github.com/stedolan/jq).  

Usage: `yt-music.sh https://www.youtube.com/watch?v=aDaoQk081IY [ALBUM] [GENRE]`  

It tries to download the file (skipping parts marked by SponsorBlock API), set correct metadata, remove suffixes from the title (e.g. “(OFFICIAL AUDIO VIDEO)” etc.), trims silence from the beginning and end, normalizes loudness to 95 dB, and finally moves the file to the destination folder.  

Should be seen as an inspiration and adopted for your needs/favorite music channels.

## Python version
The Python version is currently in beta, but will be the one I update in the future. It’s not tested extensively yet though, so there might be more bugs than in the Bash version.  
It needs [`mp3gain`](https://mp3gain.sourceforge.net/download.php) installed in your PATH.

The Python version additionally needs [YouTube OAuth2 for yt-dlp](https://github.com/coletdjnz/yt-dlp-youtube-oauth2) as was recommended in [yt-dlp/yt-dlp#10128 (comment)](https://github.com/yt-dlp/yt-dlp/issues/10128#issuecomment-2157140324).
