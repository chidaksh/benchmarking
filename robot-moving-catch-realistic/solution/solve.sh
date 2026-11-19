#!/bin/bash
# Default oracle: works from what the agent observes. It surveys the cell with the camera and with touches, catches the part, delivers it, parks and finishes.
# It uses only the robot command, numpy and Pillow. solve_recorded.sh is the recorded oracle, replayed from a plan made with the true state.
set -euo pipefail
mkdir -p /app/output
python3 /solution/oracle_from_observations.py | tee /app/output/reference.log
