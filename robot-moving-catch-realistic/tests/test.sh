#!/bin/bash
mkdir -p /logs/verifier
echo '{"functional_correctness": 0.0, "robustness": 0.0, "constraint_satisfaction": 0.0, "artifact_quality": 0.0, "overall": 0.0, "reward": 0.0}' > /logs/verifier/reward.json
cd /tests && timeout 780 python3 -I grade.py /srv/data/robot-record.json /logs/verifier
