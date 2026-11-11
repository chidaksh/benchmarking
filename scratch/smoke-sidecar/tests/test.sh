#!/bin/bash
# Passes only if /app/value.txt holds the value the server container serves.
mkdir -p /logs/verifier
echo "value.txt contents: $(cat /app/value.txt 2>&1)"
if [ "$(cat /app/value.txt 2>/dev/null)" = "sidecar-value-7341" ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
