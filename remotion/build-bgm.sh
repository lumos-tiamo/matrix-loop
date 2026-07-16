#!/usr/bin/env bash
# Procedural royalty-free lo-fi bed for the Cairn Tabs demo (SF/AgnesAI have no music model).
# Warm sustained chord-pad progression (Cmaj7→Am7→Fmaj7→G7, 4s each, looped) + soft hi-hats +
# UI "归组" blips synced to grouping moments + a quiet single-note ending. All synthesized with
# ffmpeg lavfi sources, then lowpass/tremolo/reverb for warmth. Output: out/cairn-tabs-music.mp4
set -euo pipefail
cd "$(dirname "$0")"
T=$(mktemp -d)
V=out/cairn-tabs.mp4
OUT=out/cairn-tabs-music.mp4

chord() { # $1=out  $2..$5 = freqs
  local out=$1; shift
  ffmpeg -y -loglevel error \
    -f lavfi -i "sine=frequency=$1:duration=4" \
    -f lavfi -i "sine=frequency=$2:duration=4" \
    -f lavfi -i "sine=frequency=$3:duration=4" \
    -f lavfi -i "sine=frequency=$4:duration=4" \
    -filter_complex "amix=inputs=4:normalize=1,afade=t=in:d=0.5,afade=t=out:st=3.4:d=0.6,volume=0.9" \
    -ar 44100 "$out"
}
# jazzy 7th chords (lo-fi staple)
chord "$T/c1.wav" 261.63 329.63 392.00 493.88   # Cmaj7
chord "$T/c2.wav" 220.00 261.63 329.63 392.00   # Am7
chord "$T/c3.wav" 174.61 220.00 261.63 329.63   # Fmaj7
chord "$T/c4.wav" 196.00 246.94 293.66 349.23   # G7

# concat the 16s progression, loop to ~56s, warm it up (lowpass + slow tremolo + reverb tail)
printf "file '%s'\nfile '%s'\nfile '%s'\nfile '%s'\n" "$T/c1.wav" "$T/c2.wav" "$T/c3.wav" "$T/c4.wav" > "$T/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$T/list.txt" -c copy "$T/prog.wav"
ffmpeg -y -loglevel error -stream_loop 4 -i "$T/prog.wav" -t 56 \
  -af "lowpass=f=2000,tremolo=f=5:d=0.12,aecho=0.8:0.85:220:0.25,volume=0.34,afade=t=out:st=53:d=3" \
  -ar 44100 "$T/pad.wav"

# soft hi-hat: short filtered-noise tick, one per 0.4s (offbeat feel via 0.8s bar)
ffmpeg -y -loglevel error -f lavfi -i "anoisesrc=d=0.05:c=pink:a=0.5" \
  -af "highpass=f=6000,afade=t=out:st=0.01:d=0.04,volume=0.5" -ar 44100 "$T/hat1.wav"
# lay hats across 56s every 0.4s
HAT_INPUTS=(); HAT_MAPS=""; n=0
for ms in $(seq 800 400 55000); do
  HAT_INPUTS+=(-i "$T/hat1.wav"); HAT_MAPS+="[$n:a]adelay=$ms|$ms[h$n];"; n=$((n+1))
done
MIXREFS=""; for i in $(seq 0 $((n-1))); do MIXREFS+="[h$i]"; done
ffmpeg -y -loglevel error "${HAT_INPUTS[@]}" \
  -filter_complex "${HAT_MAPS}${MIXREFS}amix=inputs=$n:normalize=0,volume=0.16" -t 56 -ar 44100 "$T/hats.wav"

# UI "归组吸附" blip: quick bright clink (sine + short decay)
ffmpeg -y -loglevel error -f lavfi -i "sine=frequency=1245:duration=0.16" \
  -af "afade=t=out:st=0.02:d=0.14,volume=0.6" -ar 44100 "$T/blip.wav"
# ending single soft note (C5)
ffmpeg -y -loglevel error -f lavfi -i "sine=frequency=523.25:duration=1.6" \
  -af "afade=t=in:d=0.05,afade=t=out:st=0.5:d=1.1,lowpass=f=2600,volume=0.4" -ar 44100 "$T/end.wav"

# blip timestamps (s) at grouping/click moments: S2 absorb, S3 x3, S4 click, S6 merge, S8 apply
BLIPS=(6.6 11.0 13.0 15.0 19.4 29.0 42.2); BI=(); BM=""; k=0
for ((i=0;i<${#BLIPS[@]};i++)); do
  ms=$(python3 -c "print(int(${BLIPS[$i]}*1000))"); BI+=(-i "$T/blip.wav"); BM+="[$i:a]adelay=$ms|$ms[b$i];"; k=$((k+1))
done
BREFS=""; for i in $(seq 0 $((k-1))); do BREFS+="[b$i]"; done
ffmpeg -y -loglevel error "${BI[@]}" -filter_complex "${BM}${BREFS}amix=inputs=$k:normalize=0,volume=0.5" -t 56 -ar 44100 "$T/blips.wav"

# ending note at ~54s
ffmpeg -y -loglevel error -i "$T/end.wav" -af "adelay=54000|54000" -t 56 -ar 44100 "$T/endm.wav"

# master mix
ffmpeg -y -loglevel error -i "$T/pad.wav" -i "$T/hats.wav" -i "$T/blips.wav" -i "$T/endm.wav" \
  -filter_complex "[0:a][1:a][2:a][3:a]amix=inputs=4:normalize=0,alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5,afade=t=in:d=1.5" \
  -ar 44100 "$T/master.wav"

# mux onto the (silent) video
ffmpeg -y -loglevel error -i "$V" -i "$T/master.wav" \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest "$OUT"
echo "BGM_OK $OUT"
rm -rf "$T"
