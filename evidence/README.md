# Evidence

The files the run report cites. None of them is needed to run the task.

## Harbor jobs

View them with `harbor view ./evidence/jobs`.

| Job folder | What it is | Reward |
|---|---|---|
| [robot-moving-catch-realistic-oracle-from-observations](jobs/robot-moving-catch-realistic-oracle-from-observations) | Default oracle, from observations | 1.0 |
| [robot-moving-catch-realistic-oracle-recorded](jobs/robot-moving-catch-realistic-oracle-recorded) | Recorded oracle | 1.0 |
| [robot-moving-catch-realistic-grader-check-do-nothing](jobs/robot-moving-catch-realistic-grader-check-do-nothing) | Grader check: an agent that does nothing | 0.0 |
| [robot-moving-catch-realistic-grader-check-tampering](jobs/robot-moving-catch-realistic-grader-check-tampering) | Grader check: the tampering test | 0.0 |
| [robot-moving-catch-realistic-run-1-claude-code-opus-5-5-high](jobs/robot-moving-catch-realistic-run-1-claude-code-opus-5-5-high) | Model run 1 | 0.0 |
| [robot-moving-catch-realistic-run-2-claude-code-opus-5-5-high](jobs/robot-moving-catch-realistic-run-2-claude-code-opus-5-5-high) | Model run 2 | 0.0 |
| [robot-moving-catch-realistic-run-3-claude-code-opus-5-5-high](jobs/robot-moving-catch-realistic-run-3-claude-code-opus-5-5-high) | Model run 3 | 0.0 |

The model runs are Claude Code with Opus 5.5 at high effort.
Their folders leave out Claude Code's raw output stream, its session state, and the agent's own working files, to keep the package small. `agent/trajectory.json` has each run.

## Analysis

Each file in [analysis-results/](analysis-results/) is what a script in [analysis-scripts/](analysis-scripts/) printed, with a first line on how to read it.

| Script | Shows | Result file |
|---|---|---|
| `catch_timing_sweep.py` on run 1 | The run catches if the grip moves to 2.37 to 2.47 s | `run1_catch_timing_sweep.txt` |
| `catch_timing_sweep.py` on run 2 | The same, for 2.40 to 2.50 s | `run2_catch_timing_sweep.txt` |
| `catch_timing_sweep.py` on run 3 | The same for its first grip, for 2.04 to 2.15 s | `run3_catch_timing_sweep.txt` |
| `rule_cases.py` | How the robot's rules score known tricks | `rule_cases.txt` |
| `grader_cases.py` | The grader on ten end states | `grader_cases.txt` |
| `run_observation_oracle.sh`, 20 draws | Default oracle: reward 1.0 on 20 of 20 | `observation_oracle_full_job_line_through_3_sightings.txt` |
| The same with `FIT=2` | Line through two sightings: 8 of 20 | `observation_oracle_full_job_line_through_2_sightings.txt` |

A draw is the same cell with a different random set of sensing errors. Draw 0 is the task's own.
`observation-oracle-records/` holds the robot's record of each of the 20 runs, and `observation-oracle-records-line-through-2/` the 20 records of the two-sighting runs.
`run2_failed_catch.png` and `run3_failed_catch.png` are the pictures in the report.

To rerun, from `evidence/analysis-scripts`, with Python, MuJoCo, NumPy and Pillow installed:

```bash
MUJOCO_GL=egl python3 -B catch_timing_sweep.py records/run-2-robot-record.json 232 238 -30 250 10
MUJOCO_GL=egl python3 -B catch_timing_sweep.py records/run-1-robot-record.json 200 201 0 500 10
MUJOCO_GL=egl python3 -B catch_timing_sweep.py records/run-3-robot-record.json 200 204 0 200 10
MUJOCO_GL=egl python3 -B rule_cases.py
MUJOCO_GL=egl python3 -B grader_cases.py
for d in $(seq 0 19); do TAG=line-through-3 ./run_observation_oracle.sh $d $((8800 + d)); done
for d in $(seq 0 19); do TAG=line-through-2 ./run_observation_oracle.sh $d $((8800 + d)) FIT=2; done
```

I ran them on the laptop, outside Docker, with Python 3.11, MuJoCo 4.0.1, NumPy 2.4.6 and Pillow 12.3.0.

## How the default oracle uses its ten setup actions

| Step | Actions | Measures |
|---|---|---|
| Look from above the track | 1 | The track's centre line |
| Close the fingers, touch the track twice | 3 | Which way is downhill |
| Look further downhill | 1 | Where the track ends |
| Touch at the catch point | 1 | The height there |
| Lift, open the fingers, look closely | 2 | The track's sideways position |
| Look from high up | 1 | The basket |
| Park | 1 | |

During the try it fits a line through its last three sightings of the part.
After the try it takes four more actions: look at the basket from above, lower, let go, park.

## The grader check

[grader-check/tampering_test.sh](grader-check/tampering_test.sh) is a test of the grader that I wrote. No agent did this.
It runs in the agent's container in place of the solution, looks for hidden files, asks the robot for hidden state, and writes forged score files.
The grader gave it 0.

## Small gaps between manual and code

None matters on the task's scene.

- Picture noise measures 1.6 percent where the manual says about 2.
- A strip up to 3 pixels wide at the picture's border repeats edge pixels.
- On other scenes of the generator, a move commanded exactly to a joint's limit can be reported as blocked.
- Two comments in `world.py` give an earlier version's step length.
