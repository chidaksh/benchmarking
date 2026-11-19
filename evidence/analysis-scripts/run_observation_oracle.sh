#!/bin/bash
# Runs the observation-based oracle against the task's real robot service on this machine, then grades the record. usage: run_observation_oracle.sh DRAW PORT [settings for the oracle]
HERE="$(cd "$(dirname "$0")" && pwd)"; DRAW=$1; PORT=$2; shift 2
OUT="$HERE/test-runs/${TAG:-untagged}"; mkdir -p "$OUT"; REC="$OUT/draw-$DRAW-record.json"; rm -f "$REC"
MUJOCO_GL=egl python3 -B "$HERE/start_robot_service.py" "$DRAW" "$PORT" "$REC" > "$OUT/draw-$DRAW-service.log" 2>&1 &
SERVICE=$!
env "$@" ROBOT_URL="http://127.0.0.1:$PORT" ROBOT_CMD="python3 -B ${ROBOT_PY:-$HERE/../../robot-moving-catch-realistic/environment/robot.py}" python3 -B -u "${SOLVER:-$HERE/../../robot-moving-catch-realistic/solution/oracle_from_observations.py}" > "$OUT/draw-$DRAW-solver.log" 2>&1
CODE=$?
kill $SERVICE 2>/dev/null
python3 - "$REC" "$DRAW" "$CODE" <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); kinds = [a["kind"] for a in r["actions"]]
cut = kinds.index("pass") if "pass" in kinds else len(kinds)
print(f"draw {sys.argv[2]}: solver exit {sys.argv[3]} | actions before the try {cut}, after {len(kinds) - cut - ('pass' in kinds)} | try stands at {r['truth']['status']} | finished {r['finished']}", end=" | ")
PY
MUJOCO_GL=egl python3 -B "$HERE/grade_test_run.py" "$DRAW" "$REC"
