#!/bin/bash
# Resumable single-piece PASCALRAW download. Aborts if free space < 6GB. Usage: dl.sh <suffix>
P=$1
D=/home/mini/dfxisp_eval_20261007/pascalraw_dl
cd "$D" || exit 2
for i in $(seq 1 200); do
  FREE=$(df -B1G --output=avail /home/mini | tail -1 | tr -d ' ')
  if [ "$FREE" -lt 6 ]; then echo "ABORT_LOW_SPACE $FREE" >> "dl_$P.log"; exit 3; fi
  curl -sL -C - --retry 5 --retry-delay 10 --max-time 600 -o "PASCALRAW.tar.gz$P" "https://stacks.stanford.edu/file/hq050zr7488/PASCALRAW.tar.gz$P"
  SZ=$(stat -c %s "PASCALRAW.tar.gz$P" 2>/dev/null || echo 0)
  echo "$(date +%T) $P size $SZ" >> "dl_$P.log"
  if [ "$SZ" -ge 10737418240 ]; then echo "COMPLETE $P" >> "dl_$P.log"; exit 0; fi
done
echo "GAVE_UP $P" >> "dl_$P.log"; exit 4
