#!/bin/bash
# Runs the pytest checks and writes the reward file.

mkdir -p /logs/verifier

if pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA; then
  score=1
else
  score=0
fi

cat > /logs/verifier/reward.json <<EOF
{"reward": $score, "overall": $score, "functional_correctness": $score, "constraint_satisfaction": $score, "robustness": $score, "artifact_quality": $score}
EOF
