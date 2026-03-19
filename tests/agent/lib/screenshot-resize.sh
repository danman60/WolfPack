#!/bin/bash
INPUT="$1"
OUTPUT="${2:-$1}"

if [ -z "$INPUT" ]; then
  echo "Usage: screenshot-resize.sh <input.png> [output.png]" >&2
  exit 1
fi

if ! file "$INPUT" 2>/dev/null | grep -q "PNG\|JPEG\|image"; then
  echo "ERROR: $INPUT is not a valid image" >&2
  exit 1
fi

DIMS=$(file "$INPUT" | grep -oP '\d+ x \d+' | head -1)
W=$(echo "$DIMS" | cut -d' ' -f1)
H=$(echo "$DIMS" | cut -d' ' -f3)

if [ "${W:-0}" -gt 1000 ] || [ "${H:-0}" -gt 2000 ]; then
  RESIZED="${INPUT%.png}_resized.png"
  if ffmpeg -y -loglevel error -i "$INPUT" \
    -vf "scale='min(1000,iw)':'min(2000,ih)':force_original_aspect_ratio=decrease" \
    "$RESIZED" 2>/dev/null; then
    mv "$RESIZED" "$OUTPUT"
    NEW_SIZE=$(stat -c%s "$OUTPUT" 2>/dev/null || echo 0)
    echo "OK: Resized ${W}x${H} -> <=1000x2000 ($(( NEW_SIZE / 1024 ))KB)" >&2
  else
    echo "WARN: ffmpeg resize failed, keeping original" >&2
    [ "$INPUT" != "$OUTPUT" ] && cp "$INPUT" "$OUTPUT"
  fi
else
  [ "$INPUT" != "$OUTPUT" ] && cp "$INPUT" "$OUTPUT"
  SIZE=$(stat -c%s "$OUTPUT" 2>/dev/null || echo 0)
  echo "OK: ${W:-?}x${H:-?} already within limits ($(( SIZE / 1024 ))KB)" >&2
fi
