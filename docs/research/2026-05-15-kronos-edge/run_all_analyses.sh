#!/usr/bin/env bash
# Drives idea1 → idea5 → idea2 → idea4 → idea3 in that order, capturing each
# script's output to results/<idea>.log. Idea3 is the slow one (GPU re-runs).
set -euo pipefail
cd /home/danman60/projects/Kronos
source venv/bin/activate
export HF_HOME=/mnt/firmament/hf-cache

ROOT=/home/danman60/projects/WolfPack/docs/research/2026-05-15-kronos-edge
LOG_DIR="$ROOT/results"
mkdir -p "$LOG_DIR"

for script in idea1_direct_strategy idea5_mtf_coherence idea2_divergence idea4_tokenizer_perplexity idea7_bollinger_baseline idea3_prob_of_touch; do
  echo
  echo "===== $script ====="
  python -u "$ROOT/${script}.py" 2>&1 | tee "$LOG_DIR/${script}.log"
done
echo
echo "ALL ANALYSES COMPLETE"
ls -la "$ROOT/results"/*.csv
