#!/bin/bash
# Parallel resumable download of ONE PASCALRAW piece into 6 part files, then verify size and cat. Usage: dlp.sh <suffix> [total_bytes]
P=$1; TOTAL=${2:-10737418240}
D=/home/mini/dfxisp_eval_20261007/pascalraw_dl
mkdir -p "$D" && cd "$D" || exit 2
N=6; CH=$(( (TOTAL + N - 1) / N ))
URL="https://stacks.stanford.edu/file/hq050zr7488/PASCALRAW.tar.gz$P"
FREE=$(df -B1G --output=avail /home/mini | tail -1 | tr -d ' ')
[ "$FREE" -lt 25 ] && { echo "ABORT_LOW_SPACE $FREE" >> "dl_$P.log"; exit 3; }
part() {
  i=$1; S=$(( i*CH )); E=$(( S+CH-1 )); [ $E -ge $TOTAL ] && E=$(( TOTAL-1 )); WANT=$(( E-S+1 ))
  for try in $(seq 1 100); do
    HAVE=$(stat -c %s "part_${P}_$i" 2>/dev/null || echo 0)
    [ "$HAVE" -ge "$WANT" ] && return 0
    curl -sL --max-time 300 -r $(( S+HAVE ))-$E "$URL" >> "part_${P}_$i"
  done
  return 1
}
for i in $(seq 0 $((N-1))); do part $i & done
wait
SUM=0; for i in $(seq 0 $((N-1))); do SUM=$(( SUM + $(stat -c %s "part_${P}_$i") )); done
echo "$(date +%T) $P parts_total $SUM expected $TOTAL" >> "dl_$P.log"
[ "$SUM" -eq "$TOTAL" ] || { echo "SIZE_MISMATCH $P" >> "dl_$P.log"; exit 4; }
cat part_${P}_0 part_${P}_1 part_${P}_2 part_${P}_3 part_${P}_4 part_${P}_5 > "PASCALRAW.tar.gz$P" && rm -f part_${P}_*
echo "COMPLETE $P $(stat -c %s PASCALRAW.tar.gz$P)" >> "dl_$P.log"
