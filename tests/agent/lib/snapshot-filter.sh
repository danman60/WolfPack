#!/bin/bash
# Filter playwright-cli snapshot to only interactive/visible elements
grep -E '(button|link |textbox|checkbox|radio|select |combobox|menuitem|tab |switch|slider|heading|cell|row |img ).*\[ref=e[0-9]+\]' \
  | sed 's/^[[:space:]]*//' \
  | head -150

echo ""
echo "--- TEXT CONTENT ---"
grep -E '^\s+- text: ' \
  | sed 's/^[[:space:]]*//' \
  | head -100
