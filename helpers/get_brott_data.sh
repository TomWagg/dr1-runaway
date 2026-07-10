#!/usr/bin/env bash
set -euo pipefail

# downloads Brott+2011 evol tracks into a single directory (flat)
BASE="http://cdsarc.u-strasbg.fr/ftp/J/A+A/530/A115"
OUTDIR="brott2011_evol"

mkdir -p "${OUTDIR}"

# grab ReadMe + models.dat (kept alongside the tracks for parsing later)
curl -fsSLo "${OUTDIR}/ReadMe"     "${BASE}/ReadMe"
curl -fsSLo "${OUTDIR}/models.dat" "${BASE}/models.dat"

# models.dat columns are fixed-width; filename is in bytes 13-33 per ReadMe
# extract the filename column and download each file from evol/
awk '{print substr($0,13,21)}' "${OUTDIR}/models.dat" \
  | sed 's/[[:space:]]*$//' \
  | grep -E '\S' \
  | sort -u \
  | while read -r fname; do
      curl -fsSLo "${OUTDIR}/${fname##*/}" "${BASE}/evol/${fname}"
    done

echo "done: downloaded $(ls -1 "${OUTDIR}"/*.dat 2>/dev/null | wc -l) track files into ${OUTDIR}"

# count how many files were downloaded
