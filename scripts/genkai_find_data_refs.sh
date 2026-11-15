#!/bin/bash
# Find which repositories under $HOME/Github refer to the undocumented Tokyo Bay archive items
# (tokyo_bay/dem_*, depth_*, kanto_*, SRTM15_*, sea_chart, osaka_bay). Read-only; uses `git grep`
# (tracked files only), so run output / data directories are skipped. Output in the job log.
#   pjsub -o logs/find_data_refs.%j.log scripts/genkai_find_data_refs.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=2
#PJM -L elapse=00:20:00
#PJM -j
#PJM -X
set -uo pipefail
cd "${HOME}/Github"
PAT='tokyo_bay/(dem_|depth_|kanto_|SRTM15_|\.om_dem)|bathymetry/(sea_chart|osaka_bay)|dem_[0-9]{2}_0[1-4]_|depth_0(030|090|270|810)|SRTM15_(kanto|pacific)|kanto_M7001'
for d in */; do
  d=${d%/}
  [ -d "$d/.git" ] || [ -f "$d/.git" ] || { echo "-- $d: not a git repo, skipped"; continue; }
  echo "-- $d"
  timeout 120 git -C "$d" grep -I -n -E "$PAT" -- . 2>/dev/null > "/tmp/refs_$$.txt" || true
  echo "   hits: $(wc -l < /tmp/refs_$$.txt)"
  cut -c1-200 "/tmp/refs_$$.txt" | head -12
done
rm -f "/tmp/refs_$$.txt"
echo "=== done"
