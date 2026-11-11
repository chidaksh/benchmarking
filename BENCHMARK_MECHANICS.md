# Harbor mechanics for a small "Claude Code fails" benchmark

Follow-up to `SETUP_NOTES.md`, same environment (Harbor 0.25.0, Docker 29.9.2).
No model was called and no API key was used.
Every run below used `oracle`, `nop`, or a model-free probe agent (`scratch/probe-agent/probe_agent.py`).
Items marked "from code reading" were not exercised by a run.

## What matters most, in order

1. Use `[verifier] environment_mode = "separate"`.
   In shared mode an agent can fake a pass (confirmed below).
2. Write a single binary key, `{"reward": 0 or 1}`, if you want Harbor's pass@k.
   Put sub-scores in a separate file that Harbor does not read.
3. Treat verifier exceptions as bugs, not as failures.
   Harbor counts them as 0 in the mean, so a broken test looks exactly like "Claude failed".
4. An agent timeout is not a failure by itself.
   The verifier still grades whatever state the agent left.
5. Validate every task with `oracle` (must score 1), `nop` (must score 0), and the probe agent (must score 0) before spending money on Claude.

## 1. What the agent can see (probe agent, confirmed)

The probe agent runs shell commands in the agent container instead of calling a model.

```
PYTHONPATH=scratch/probe-agent harbor run -p scratch/smoke-basic -a probe_agent:ProbeAgent
```

Its output is saved to `jobs/<job>/<trial>/agent/probe.txt`.
Findings from `jobs/2026-11-11__19-45-48`:

- The agent runs as `uid=0(root)` with cwd `/app`, unless the task sets `[agent] user`.
- `/tests` and `/solution` do not exist during the agent phase.
  The oracle uploads `/solution` itself (`harbor/agents/oracle.py`), and tests are only uploaded for the verifier.
- `/logs/agent`, `/logs/verifier` and `/logs/artifacts` exist and are world-writable (`drwxrwxrwx`).
- The environment has only `HOME HOSTNAME PATH PWD SHLVL`.
  Task files outside `environment/` (README, solution, tests) are not in the image.
- The instruction is exactly the text of `instruction.md`.

## 2. Reward tampering (confirmed)

The probe agent tries three things:
- writing `{"reward": 1}` to `/logs/verifier/reward.json` and `1` to `reward.txt`
- overwriting `/tests/test.sh`, if present
- leaving a background loop that rewrites `/logs/verifier/reward.txt` every 0.05s

| Task | Verifier mode | Correct answer present? | Reward |
|------|---------------|-------------------------|--------|
| smoke-sidecar | shared | no | 1.0 (fooled) |
| smoke-basic | separate | no | 0 (not fooled) |

Shared mode, `jobs/2026-11-11__19-46-37`.
The test printed `value.txt contents: cat: /app/value.txt: No such file or directory` and wrote 0, but the final reward file said 1.

Harbor deletes old reward files before the test runs (`_remove_reward_files` in `harbor/verifier/verifier.py`).
It does not kill processes the agent left behind, so the loop overwrote the test's result.
The direct writes alone would not have worked, because they were deleted.
Also note that `reward.json` wins over `reward.txt` when both exist, so a loop writing `reward.json` would win as well.

In separate mode (`jobs/2026-11-11__19-47-20`) the verifier runs in a fresh container that receives only the declared `artifacts`, so none of this reaches it.
Claude Code is unlikely to do this on purpose, but a "Claude fails" benchmark needs its passes to be trustworthy too.

## 3. Verifier failure handling (confirmed)

Four oracle tasks in `scratch/verifier-edge-cases`, run as one job (`harbor run -p scratch/verifier-edge-cases -a oracle -n 4`, `jobs/2026-11-11__19-48-34`):

| Task | What it does | Trial rewards | Exception |
|------|--------------|---------------|-----------|
| t-exit1 | test.sh writes reward 1 then `exit 1` | `{'reward': 1.0}` | none |
| t-noreward | test.sh writes no reward file | `None` | `RewardFileNotFoundError` |
| t-badreward | writes `{"reward": "yes"}` | `None` | `VerifierOutputParseError: Non-numeric reward 'yes' ...` |
| t-timeout | `[agent] timeout_sec = 5`, solve.sh writes the answer then sleeps 30 | `{'reward': 1, ...}` | `AgentTimeoutError: Agent execution timed out after 5.0 seconds` |

Job summary: `Trials 2`, `Exceptions 3`, mean `reward` 0.500.
So the mean was (1 + 1 + 0 + 0) / 4.

What this means:
- The test script's exit code is ignored.
  Only the reward file counts, so a test that crashes after writing a pass still passes.
  Use `set -e` and write the reward last.
- A trial with a verifier error gets `rewards = None`, and `harbor/metrics/base.py` (`aggregate_reward_dicts`) counts `None` and missing keys as 0.
  Always read the Exceptions table, and rerun or fix any `RewardFileNotFoundError` or `VerifierOutputParseError` before calling a task a Claude failure.
- After an agent timeout, the verifier still runs and the reward is recorded, alongside the exception.
  If Claude runs out of time after half-solving the task, the partial state is graded.
  Decide whether that is what you want.
  It is also a good reason to set `[agent] timeout_sec` generously, so that a failure is about ability and not about the clock.
- A missing artifact (agent never created `/app/answer.txt`) is logged in `trial.log` as `Engine cp failed ... Could not find the file`, but it is not a trial exception.
  The `nop` run on smoke-basic had 0 exceptions and reward 0.
- Retries are off by default (`--max-retries 0`).
  If you turn them on, `--retry-include` defaults to every exception type, which would re-run Claude after an `AgentTimeoutError` and cost money.
  Use `--retry-exclude AgentTimeoutError` or a narrow `--retry-include`.

## 4. Repeated attempts and pass@k (confirmed plus code reading)

`harbor run -p scratch/smoke-sidecar -a oracle -k 3 -n 3` produced 3 trials and `pass_at_k {'2': 1.0}` (`jobs/2026-11-11__19-49-28`).

From `harbor/utils/pass_at_k.py`:
- pass@k is computed only if every trial's reward has exactly one key, with value 0 or 1.
  A multi-key `reward.json` silently gives `pass_at_k {}`.
  A reward of 0.5 also disables it.
- The k values reported are 2, 4, 8, ... and 5, 10, 15, ..., up to the smallest number of attempts on any task.
  `-k 3` gives only pass@2, and `-k 5` gives pass@2, pass@4 and pass@5.
- Errored trials count as failures (0).
- With a single key, the summary metric is named `mean`, not `reward`.

For a "fails" benchmark with few samples, `-k 5` per task is a reasonable minimum to separate "always fails" from "fails sometimes".
That is not something I could test without running Claude.

## 5. Claude Code install (confirmed with a test-only workaround)

```
harbor run -p <task> -a claude-code -m anthropic/claude-opus-5-5 --install-only --skip-credential-checks
```

`--install-only` builds the environment, installs the agent, and exits without running it or the verifier.
It makes no API call.

- In this cloud container it first failed with `NetworkConnectionError` ... `curl: (60) SSL certificate problem: self-signed certificate in certificate chain`.
  That is this environment's TLS proxy, the same cause as the hello-world failure.
- With a scratchpad-only copy of the task whose image trusts the proxy certificate, it succeeded.
  `agent_info` showed `{'name': 'claude-code', 'version': '2.1.322', ...}`.
  Setup took about 2 minutes (`apt-get install -y curl nodejs npm`, then the bootstrap script).
  That copy is not committed, and you should not need it on a laptop.
- Harbor skips the install when `claude` is already on PATH at the requested version (`_installed_claude_satisfies_version`).
  Preinstalling Claude Code in `environment/Dockerfile` would save those 2 minutes per trial.
  I did not test that.
- Pin the version with `--ak version=2.1.322` (or whatever you choose) so all trials use the same Claude Code build.

## 6. Agent options (dry run and print-config, confirmed)

```
harbor run -p scratch/smoke-basic -a claude-code -m anthropic/claude-opus-5-5 \
  --effort high --ak version=2.1.322 --ak max_turns=200 \
  --ae CLAUDE_CODE_DISABLE_1M_CONTEXT=1 -k 5 --dry-run
```

Output ends with `Dry run OK - 5 trial(s); nothing was run.`

`--print-config` with the same flags shows how they are resolved:

```json
{
  "name": "claude-code",
  "model_name": "anthropic/claude-opus-5-5",
  "kwargs": {"version": "2.1.322", "max_turns": 200, "reasoning_effort": "high"},
  "env": {"CLAUDE_CODE_DISABLE_1M_CONTEXT": "1"}
}
```

- `--ak` names are checked.
  `--ak max_turnz=5` fails with `Unknown option 'max_turnz'. See harbor agent schema claude-code for available options.`
- `--ae` values are not checked; any `KEY=VALUE` is accepted.
  From code reading, they are added to the environment of every command the agent runs (`exec_env = self.agent.extra_env` in `harbor/trial/trial.py`).
  So `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` should reach Claude Code, but I could not confirm that without a real run.
- `harbor agent schema claude-code` lists every option.
  Defaults worth knowing: `permission_mode` is `bypassPermissions`, and `max_turns`, `max_budget_usd` and `reasoning_effort` are unset.
- Record the exact command, Claude Code version, effort and context setting with each result, since all of them change what "fails" means.

## 7. Things I did not run

- `harbor check` grades task quality with an LLM (default `-a claude-code -m claude-sonnet-4-6`), so it costs money.
  I skipped it.
- Any real Claude Code run, so nothing here shows how Claude actually behaves on a task.
- A non-root `[agent] user` (lint's `root-agent` rule recommends one).
- Multi-step tasks (`harbor task init --steps N`).
- `harbor task init --include-canary-strings`, which adds contamination canaries to task files.

## Commands to validate a new task before any paid run

```bash
harbor lint <task>                       # default rules
harbor lint --select ALL <task>          # pinning, root agent, network downloads in the verifier
harbor run -p <task> -a oracle -k 3      # must be 1.0 every time (flakiness check)
harbor run -p <task> -a nop              # must be 0
PYTHONPATH=scratch/probe-agent harbor run -p <task> -a probe_agent:ProbeAgent   # must be 0
harbor run -p <task> -a claude-code -m anthropic/claude-opus-5-5 --install-only --skip-credential-checks
harbor run -p <task> -a claude-code -m anthropic/claude-opus-5-5 --effort high --ak version=<pinned> -k 5 --dry-run
# then check the Exceptions table of every job: only AgentTimeoutError is expected
```
