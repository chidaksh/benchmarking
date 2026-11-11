#!/bin/bash
# Smoke verifier: checks /app/answer.txt and writes a multi-key reward.json.
# Values are deliberately different from each other so the reported key is identifiable.
mkdir -p /logs/verifier
if [ "$(cat /app/answer.txt 2>/dev/null)" = "hello harbor" ]; then
  R=1
else
  R=0
fi
cat > /logs/verifier/reward.json <<JSON
{"reward": $R, "overall": 0.5, "functional_correctness": 0.9, "constraint_satisfaction": 0.8, "robustness": 0.7, "artifact_quality": 0.6}
JSON
cat /logs/verifier/reward.json
