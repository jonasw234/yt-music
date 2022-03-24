#!/usr/bin/env zsh
# set -x
# Helpers
error() {
    echo "\e[0;31m$1\e[0;39m"
}
warning() {
    echo "\e[0;33m$1\e[0;39m"
}

# Check for requirements
(which yt-dlp; which titlecase; which mp3splt; which mp3gain; which eyeD3; which jq) | grep ' not found$' || found_everything=1
if [[ -z "$found_everything" ]]; then
    error "One or more commands not found.  Check the error message above."
    exit 2
fi

# Print usage information
if (( $# < 1 || $# > 3)); then
    error "Usage: $0 https://www.youtube.com/watch?v=aDaoQk081IY [ALBUM] [GENRE]"
    exit 1
fi

# Download file
filename=$(yt-dlp --no-playlist --write-info-json --extract-audio --sponsorblock-remove all --audio-format mp3 -o "%(title)s.%(ext)s" "$1" | awk -F': ' '/\[ExtractAudio\] Destination: / {print $2}')
if [[ -z $filename ]]; then
    error 'Apparently there was a problem downloading the video.'
    exit 2
fi
infofile="${filename%.*}.info.json"

# Normalize filename
new_filename=$(print -r -- "${(L)filename}")
new_filename=${new_filename/ \($(date +'%Y')\)/}
new_filename=${new_filename/ _ afm records/}
new_filename=${new_filename/ _ official audio video/}
new_filename=${new_filename/ _ official lyric video/}
new_filename=${new_filename/ _ official music video/}
new_filename=${new_filename/ _ napalm records/}
new_filename=${new_filename/_ napalm records/}
new_filename=${new_filename/ \(lyric video\)/}
new_filename=${new_filename/ \(official animated video\)/}
new_filename=${new_filename/ \(official lyric video\)/}
new_filename=${new_filename/ \(official lyrics video\)/}
new_filename=${new_filename/ \(official music video\)/}
new_filename=${new_filename/ \(official video\)/}
new_filename=${new_filename/ \[official video\]/}
new_filename=${new_filename/ – official video clip/}
new_filename=${new_filename/ \(official\)/}
new_filename=${new_filename/ \(audio\)/}
new_filename=${new_filename/ \(offizielles video\)/}
new_filename=${new_filename/ \(official audio\)/}
new_filename=${new_filename/ \(hq\)/}
new_filename=${new_filename/ \(official visualizer\)/}
new_filename=${new_filename/ \(music video\)/}
new_filename=${new_filename/ \(ft./ \(feat.}
new_filename=${new_filename/ ft./ feat.}
new_filename=${new_filename/ \($(date +%Y)\)/}
new_filename=${new_filename//"'"/’}
# Extract artist and title from the filename
artist=$(echo -n "$new_filename" | awk -F' -' '{print $1}' | titlecase)
title=$(echo -n "$new_filename" | sed 's/\.mp3//' | awk -F'- ' '{print $2}' | titlecase)

# Sometimes artists have their own channel and publish songs only with the title
if [[ -z $title ]]; then
    title=$(echo "$artist" | sed 's/\.mp3//')
    artist=$(jq .uploader < "$infofile" | titlecase)
    artist=${artist:1:-1}
fi

# Trim silence at beginning and end
mp3splt -qnr "$filename" -o 'trimmed' > /dev/null
mv 'trimmed.mp3' "$filename"

# Set tags
year=$(jq .upload_date < "$infofile")
year=${year:1:4}
warning "Used upload date as publication date: $year"
eyeD3 -a "$artist" -t "$title" --text-frame TYER:"$year" "$filename" >/dev/null
if [[ -d "$DESTINATION/$artist" ]]; then
    old_artist="$artist"
    artist=$(find "$DESTINATION" -iname "$artist" 2>/dev/null | cut -c "$((${#DESTINATION}))-" | tr -d '/')
    if [[ "$artist" != "$old_artist" ]]; then
        warning "Using previous casing instead of default one: $artist"
        eyeD3 -a "$artist" "$filename" >/dev/null
    fi
    genre=$(eyeD3 "$(find "$DESTINATION/$artist/" -iname \*.mp3 | head -1)" >/dev/null | awk -F': ' '/genre/ {print $3}' | sed 's/ (id .*)//')
    warning "Using existing references for genre: $genre"
    eyeD3 --text-frame TCON:"$genre" "$filename" >/dev/null
else
    if [[ ! -z "$3" ]]; then
        warning "Using genre supplied by user: $3"
        eyeD3 --text-frame TCON:"$3" "$filename" >/dev/null
    else
        error 'Still missing genre tag (no reference files found)'
    fi
fi
if [[ ! -z "$2" ]]; then
    warning "Using album title supplied by user: $2"
    eyeD3 -A "${(C)2}" "$filename" >/dev/null
else
    album=$(jq .description < "$infofile" | cut -d '"' -f 3)
    if jq .uploader_id < "$infofile" | grep -q 'NuclearBlastEurope' && album="$(jq .description < "$infofile" | cut -d ',' -f 2) "; then
        error 'Couldn''t extract album from description.'
    elif [[ ! -z $album ]]; then
        album=${(C)album:0:-1}
        album=${album/"'"/’}
        warning "Extracted album from description: $album"
        eyeD3 -A "$album" "$filename" >/dev/null
    else
        error 'Couldn''t extract album from description.'
    fi
fi

# Info file is no longer needed
rm "$infofile"

# Normalize loudness to 95 dB
mp3gain -c -r -d 6 "$filename" > /dev/null

# Create folder (if needed) and move file
mkdir "$YT_MUSIC_PATH/$artist" 2>/dev/null
cp "$filename" "$YT_MUSIC_PATH/$artist/$title.mp3" && rm "$filename"
[ -x wslpath ] && echo "Copied to $YT_MUSIC_PATH/$artist/$title.mp3" || echo -E "Copied to $(wslpath -w "$YT_MUSIC_PATH/$artist/$title.mp3")"
