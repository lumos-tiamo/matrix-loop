#!/usr/bin/env bash
# Audio bed for the Cairn Tabs demo. Default = ONLY the "叮" UI clicks (no background music).
# Set BGM=1 to also lay the lo-fi chord-pad + hats bed under the blips.
# Blips are synced to: the tab-group snaps (S3), each cursor click (S4/S6/S7/S9), and the
# cairn-logo stacking (S10). Output: out/cairn-tabs-music.mp4
set -euo pipefail
cd "$(dirname "$0")"
T=$(mktemp -d)
V=out/cairn-tabs.mp4
OUT=out/cairn-tabs-music.mp4
BGM=${BGM:-0}
DUR=60

# ---- the "叮" clink (bright sine + fast decay) --------------------------------------
ffmpeg -y -loglevel error -f lavfi -i "sine=frequency=1245:duration=0.18" \
  -af "afade=t=out:st=0.02:d=0.16,volume=0.85" -ar 44100 "$T/blip.wav"

# blip timestamps (s): S3 group snaps ×3 · 归类 · 星标 · 搜索 · 归档 · 玛尼堆叠石 ×3
BLIPS=(11.5 13.0 14.5 20.2 30.67 35.33 49.47 55.0 55.8 56.6)
BI=(); BM=""; k=0
for ((i=0;i<${#BLIPS[@]};i++)); do
  ms=$(python3 -c "print(int(${BLIPS[$i]}*1000))")
  BI+=(-i "$T/blip.wav"); BM+="[$i:a]adelay=$ms|$ms[b$i];"; k=$((k+1))
done
BREFS=""; for i in $(seq 0 $((k-1))); do BREFS+="[b$i]"; done
ffmpeg -y -loglevel error "${BI[@]}" \
  -filter_complex "${BM}${BREFS}amix=inputs=$k:normalize=0,volume=0.9" -t $DUR -ar 44100 "$T/blips.wav"

if [[ "$BGM" == "1" ]]; then
  # ---- optional lo-fi chord-pad bed (Cmaj7→Am7→Fmaj7→G7) + soft hats -------------
  chord() { local out=$1; shift
    ffmpeg -y -loglevel error -f lavfi -i "sine=frequency=$1:duration=4" -f lavfi -i "sine=frequency=$2:duration=4" \
      -f lavfi -i "sine=frequency=$3:duration=4" -f lavfi -i "sine=frequency=$4:duration=4" \
      -filter_complex "amix=inputs=4:normalize=1,afade=t=in:d=0.5,afade=t=out:st=3.4:d=0.6,volume=0.9" -ar 44100 "$out"; }
  chord "$T/c1.wav" 261.63 329.63 392.00 493.88
  chord "$T/c2.wav" 220.00 261.63 329.63 392.00
  chord "$T/c3.wav" 174.61 220.00 261.63 329.63
  chord "$T/c4.wav" 196.00 246.94 293.66 349.23
  printf "file '%s'\nfile '%s'\nfile '%s'\nfile '%s'\n" "$T/c1.wav" "$T/c2.wav" "$T/c3.wav" "$T/c4.wav" > "$T/list.txt"
  ffmpeg -y -loglevel error -f concat -safe 0 -i "$T/list.txt" -c copy "$T/prog.wav"
  ffmpeg -y -loglevel error -stream_loop 4 -i "$T/prog.wav" -t $DUR \
    -af "lowpass=f=2000,tremolo=f=5:d=0.12,aecho=0.8:0.85:220:0.25,volume=0.34,afade=t=out:st=57:d=3" -ar 44100 "$T/pad.wav"
  ffmpeg -y -loglevel error -i "$T/pad.wav" -i "$T/blips.wav" \
    -filter_complex "[0:a][1:a]amix=inputs=2:normalize=0,alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5,apad" -t $DUR -ar 44100 "$T/master.wav"
else
  # ---- blips only: boost the clicks to an audible level, cap with a limiter, keep the silence
  # between them (no loudnorm — it would pump the gaps), pad to full length so mux won't truncate.
  ffmpeg -y -loglevel error -i "$T/blips.wav" -af "volume=4,alimiter=limit=0.6,apad" -t $DUR -ar 44100 "$T/master.wav"
fi

# mux onto the (silent) video
ffmpeg -y -loglevel error -i "$V" -i "$T/master.wav" \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest "$OUT"
echo "AUDIO_OK ($([[ "$BGM" == "1" ]] && echo 'music+blips' || echo 'blips only')) $OUT"
rm -rf "$T"
