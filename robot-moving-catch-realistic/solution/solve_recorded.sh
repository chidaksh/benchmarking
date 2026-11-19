#!/bin/bash
# Recorded oracle: replays a list of robot actions that was planned from the true state of the cell.
set -euo pipefail
mkdir -p /app/output
python3 /solution/replay.py | tee /app/output/reference.log
