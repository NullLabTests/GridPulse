#!/usr/bin/env bash
# Offline reproducible smoke test for GridPulse M1
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
python3 -m gridpulse.cli run --synthetic --out-dir experiments/m1_synthetic
echo "Synthetic benchmark complete. See experiments/m1_synthetic/"
