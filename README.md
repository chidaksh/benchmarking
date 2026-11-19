# robot-moving-catch-realistic

| Path | What it is |
|---|---|
| [robot-moving-catch-realistic/](robot-moving-catch-realistic/) | The Harbor task. The results are in its [RUN_REPORT.md](robot-moving-catch-realistic/RUN_REPORT.md) |
| [evidence/](evidence/) | Run logs and the analysis behind the report. See its [README](evidence/README.md) |

## My experience working on the task, approach and final method

1. I started with tasks in other areas, like tax returns (because VALS tax bench showed Opus 5.5 with claude code harness was weak). But my tasks involved programmatic judges and the system passed every one of them.

2. The main reason for not able to find a failure mode after few tries was that - the agent could check its own answer and keep fixing it. It was writing its own verifier logic and hence passing the task with correct solution. I tried few things like chaining tax filing across years, etc but as predicted it just increased number of tokens, time of solving the task but they eventually solved it.

3. The other factor of difficulty was not being able to use time as a capability factor. I wanted to give good amount of time as mentioned in doc (no time failures). So tasks such as finish task X in time k were not possible, although there can be debate saying such tasks can also be part of the capability benchmarks.

4. Tasks such as humor, deception are generally harder for models to gauge but they need an LLM judge to evaluate them, which I chose not to use. I didn't want to use agentic judges as well because of reproducibility, cost and importantly I was curious to find a task with programmatic verifier itself. So I moved to a robot, where the agent has to act on a scene it cannot fully measure - POMDP kind of setups, where errors can propagate

5. To make the task realistic, long-horizon - I first tried bin picking puzzles where I created one, which the agent was able to solve after lot of thinking. So I decided to make it hard and that's when I got an idea of catching a rolling object. Because here even if it wants to build a verifier to test the solution - it has to encode the physics correctly which is much more difficult unlike simple deterministic verifiers

6. I also thought of weight space programming benchmark - ability to reason about the given failure in a network, edit few weights accordingly and ensure the capaibility is removed or improved. But that needed gpus for getting the unlearned checkpoints and felt under the worktest definitions would become unfair (asking not to use optimziers)

## Decisions I made, and why

1. The try starts from the park pose and the manual says nothing about the part. Otherwise the agent just parks the hand at the best spot and the catch becomes two commands.

2. The robot never says "caught" or "foul". This robot's gripper reports only how far it is open, as simple industrial grippers do, so the agent has to judge the result itself.

3. Robot time is paused while the model thinks. I didn't want to test how fast the model answers, only how well it decides.

4. An action takes effect one step late and a move cannot be changed once sent. I modelled this on point-to-point joint moves and camera delay on industrial arms, and it forces the agent to predict.

5. I kept the grip firm. A slippery grip would fail the agent for something it cannot control, since it sets neither the finger force nor the arm speed.

## What I would do next

1. The current cylinder object length is close to the track's width - which tells the agent the part's size before it sees it, and I did not intend that. I want to make the track wider and ensure the physics such that objects with lower width can be released

2. I want to attempt for 3 tries instead of single pass/fail run - give it three tries but each item a new object falls from top, with unknown dimensions. This would test whether it adapts after a failed try, and I would test a changing size separately. We can also bring friction into play to make it more realistic, if the agent is also allowed to set the grip force

3. The current time for each run is heavy (greater than 120 mins for run 3). One thing to test is to give the agent a picture only every third step, so that each decision has to plan three steps ahead without seeing the part in between, but that will be a much harder task, and I do not know yet if it would be faster