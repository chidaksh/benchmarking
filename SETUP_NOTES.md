# Harbor setup checks

Date of run: 2026-11-11, in a Claude Code cloud container (Linux, Docker 29.9.2, Harbor 0.25.0).
All actual runs used the `oracle` agent.
No model trial was run, and no API key was present in the environment.
Everything marked PASS below was run and seen to pass in this session.
Statements marked "from code reading" were not exercised by a run.

## Summary

| # | Check | Result |
|---|-------|--------|
| 1 | Docker | PASS after starting `dockerd` by hand and adding a registry mirror |
| 2 | Install | PASS, Harbor 0.25.0 |
| 3 | hello-world with oracle | RAN, but reward 0.0 because of this container's TLS proxy, not Harbor |
| 4 | Basic task, oracle, lint | PASS |
| 5 | reward.json keys | PASS, `reward` is the primary score |
| 6a | Sidecar, default network | PASS |
| 6b | Sidecar, allowlist without the service | FAIL as expected (blocked) |
| 6c | Sidecar, allowlist plus the service | PASS only when the sidecar service declares `networks:` explicitly |
| 6d | Sidecar, no-network | FAIL as expected (blocked) |
| 7 | Dry runs | `-a claude-code` forms accepted, `-a claude` rejected |
| 8 | Claude Code agent inspection | Done, details below |

## 1. Docker

Command and first result:

```
$ docker info
...
Server:
failed to connect to the docker API at unix:///var/run/docker.sock; check if the path is correct and if the daemon is running: dial unix /var/run/docker.sock: connect: no such file or directory
```

The daemon was not running.
I started it in the background with no options:

```
nohup dockerd > dockerd.log 2>&1 &
```

After that `docker info` reported `Server Version: 29.9.2`, `Storage Driver: overlayfs`.

A second problem showed up on the first pull: Docker Hub refused anonymous pulls from this container's egress IP.

```
$ docker run --rm hello-world
docker: Error response from daemon: unknown: failed to resolve reference "docker.io/library/hello-world:latest": unexpected status from HEAD request to https://registry-1.docker.io/v2/library/hello-world/manifests/latest: 429 Too Many Requests
```

Fix: I configured Google's public Docker Hub mirror and restarted the daemon.

```
echo '{"registry-mirrors": ["https://mirror.gcr.io"]}' > /etc/docker/daemon.json
pkill dockerd; nohup dockerd > dockerd.log 2>&1 &
```

After this, `docker run --rm hello-world` pulled and ran.
This is still the local Docker environment, not a different sandbox provider.
On a laptop with a logged-in Docker Hub account this step should not be needed.

Result: PASS (with the two workarounds above).

## 2. Install

```
$ uv tool install harbor
...
Installed 3 executables: harbor, hb, hr
$ harbor --version
0.25.0
```

Package location: `/root/.local/share/uv/tools/harbor/lib/python3.13/site-packages/harbor`.

Result: PASS.

## 3. Hello world

```
$ harbor run -t hello-world/hello-world -a oracle
  1/1 Mean: 0.000 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0:00:29 0:00:00
adhoc • oracle
│      1 │          0 │ 0.000 │
...
Results written to jobs/2026-11-11__18-54-22/result.json
```

The run completed with no exception, but the reward was 0.0.
The oracle itself succeeded (`agent/oracle.txt` contains `Done!`).
The verifier failed while bootstrapping its own tools.
From `verifier/test-stdout.txt`:

```
curl: (60) SSL certificate problem: self-signed certificate in certificate chain
/tests/test.sh: line 8: /root/.local/bin/env: No such file or directory
/tests/test.sh: line 11: uvx: command not found
```

The hello-world `tests/test.sh` downloads `uv` from `astral.sh` at verify time.
This container sends all outbound HTTPS through a TLS-intercepting proxy whose CA is not trusted inside task containers, so that download fails.
This is a property of this cloud environment, not of Harbor.
I expect hello-world to score 1.0 on a normal laptop, but I could not verify that here.

Where output lands: `jobs/<YYYY-MM-DD__HH-MM-SS>/` relative to the current directory.
Inside a job directory:

```
jobs/2026-11-11__18-54-22/
  config.json  job.log  lock.json  result.json
  hello-world__7tuXC4W/
    config.json  lock.json  result.json  trial.log
    agent/oracle.txt
    artifacts/manifest.json
    verifier/test-stdout.txt  verifier/reward.txt
```

Downloaded registry tasks are cached under `~/.cache/harbor/tasks/packages/`.

Result: the run mechanics work.
The reward of 0.0 is caused by the environment, so I am not counting hello-world as a pass.

## 4. Basic task and lint

Commands:

```
harbor task init smoke/smoke-basic -p scratch --no-pytest \
  --description "Smoke test task" --author "Smoke Tester <smoke@example.com>"
# edited instruction.md, solution/solve.sh, tests/test.sh, task.toml (see scratch/smoke-basic)
harbor lint scratch/smoke-basic           # no output, exit 0
harbor lint --json scratch/smoke-basic    # []
harbor run -p scratch/smoke-basic -a oracle
```

The oracle run scored `reward` 1.0 with 0 exceptions (job `jobs/2026-11-11__18-56-34`).

Things `task init` generated that are worth knowing:

- `[verifier] environment_mode = "separate"` is the default.
  The verifier runs in its own container built from `tests/Dockerfile`.
  Files the agent produced only reach it if they are listed in `artifacts`.
  I set `artifacts = ["/app/answer.txt"]` and the file was re-created at the same path in the verifier container.
- Network policy defaults to `[environment] network_mode = "public"`.
- The generated `tests/test.sh` comment says `rewards.json`, but the file Harbor actually reads is `/logs/verifier/reward.json` (see `harbor/models/trial/paths.py`: `reward_json_path = verifier_dir / "reward.json"`).

Layout question.
The generated and accepted layout is:

```toml
schema_version = "1.4"
artifacts = ["/app/answer.txt"]

[task]
name = "smoke/smoke-basic"
version = "1.0.0"
description = "Smoke test task"
keywords = []
[[task.authors]]
name = "Smoke Tester"
email = "smoke@example.com"

[metadata]
```

I linted copies of the task with variations.
Each line shows the change and the lint result.

| Variant | Lint result |
|---------|-------------|
| `schema_version = "1.4"` (generated) | clean, exit 0 |
| `schema_version = "1.0"` | clean |
| `schema_version = "9.9"` | clean, so lint does not validate the value |
| `version = "1.0"` at top level (old hello-world style) | clean, it is silently renamed to `schema_version` |
| `[task] authors = [{ name = "...", email = "..." }]` inline | clean |
| `[task] authors = ["Smoke Tester"]` (plain strings) | exit 1, `[invalid-task-config] task.authors.0: Invalid configuration (model_type)` |
| no `[task]` authors, `[metadata] author_name = ...`, `author_email = ...` | clean |
| `[metadata] authors = [{...}]` | clean |
| `authors = [...]` at top level | exit 1, `[unknown-config-field] Unknown field 'authors'` |

Conclusion:
- Use `schema_version = "1.4"`, which is the default in `TaskConfig` (`schema_version: str = "1.4"` in `harbor/models/task/config.py`).
- Author metadata belongs under `[task] authors`, as a list of tables with `name` and optional `email`.
  That is the only place where authors are a typed field (`PackageInfo.authors: list[Author]`).
- `[metadata]` is an untyped `dict[str, Any]`, so lint accepts anything there.
  It is not an error, but it is not where Harbor looks for authors.
  The registry hello-world task has both, which is probably where the docs contradiction comes from.

With `--select ALL`, lint also reports these non-default rules on the basic task:

```
unpinned-image  environment/Dockerfile  FROM: Pin the external image to a SHA-256 digest.
root-agent      task.toml               agent.user: Agent user is omitted or root; configure a non-root user.
unpinned-image  tests/Dockerfile        FROM: Pin the external image to a SHA-256 digest.
```

`[agent] network_mode = "allowlist"` with `allowed_hosts = ["api.anthropic.com"]` also lints clean.

Result: PASS.

## 5. Reward file

`scratch/smoke-basic/tests/test.sh` writes, with deliberately different values so each key is identifiable:

```json
{"reward": 1, "overall": 0.5, "functional_correctness": 0.9, "constraint_satisfaction": 0.8, "robustness": 0.7, "artifact_quality": 0.6}
```

Run output (job `jobs/2026-11-11__18-56-34`):

```
┃ Trials ┃ Except… ┃ Artifa… ┃ Constr… ┃ Functio… ┃ Overall ┃ Reward ┃ Robust… ┃
│      1 │       0 │   0.600 │   0.800 │    0.900 │   0.500 │  1.000 │   0.700 │
```

The job `result.json` stores every key under `stats.evals.oracle__adhoc.metrics[0]` as a per-key mean.
So the CLI summary shows all keys side by side and does not pick one.

Which key is "the" score: `reward`.
Several places in Harbor single it out:

- `harbor/cli/jobs.py:2885`, `_primary_reward`: returns `rewards["reward"]` if present, otherwise the only value if there is exactly one key, otherwise `None`.
- `harbor/upload/uploader.py:780`: the same rule for uploads.
- `harbor/telemetry.py:967`: `rewards.get("reward")`.
- `harbor/viewer/server.py:1827`: `rewards.get("reward", 0)`.

Without `reward` (a scratchpad copy whose test.sh writes `{"overall": 1, "functional_correctness": 0.9, ...}`, not committed):

```
┃ Trials ┃ Exceptio… ┃ Artifact… ┃ Constrai… ┃ Function… ┃ Overall ┃ Robustne… ┃
│      1 │         0 │     0.600 │     0.800 │     0.900 │   1.000 │     0.700 │
```

There was no error and no warning.
The trial still completes and all keys are still reported.
But there is no `Reward` column, and from code reading the primary-reward helpers above return `None` for this trial because there is more than one key.
The viewer would show 0.
So `overall` is not treated as a fallback.
If you want one headline score, write it as `reward` (it can be the same number as `overall`).

Result: PASS.

## 6. Two containers

Task: `scratch/smoke-sidecar`.
`environment/docker-compose.yaml` adds a service named `server` next to `main`.
`server` is `python:3.12-slim` running `python3 -m http.server 8000` and serving `/srv/value.txt` containing `sidecar-value-7341`.
The oracle fetches `http://server:8000/value.txt` and writes `/app/value.txt`.
The verifier (shared mode) checks the file content.
Each variant only changed the `[agent]` block in `task.toml`.

### How Harbor enforces network policy on Docker (from code reading)

When any policy is not `public`, Harbor adds an egress-control sidecar (`harbor-docker-egress-control-sidecar`, nftables plus a gost proxy).
It then forces `main`, and every service in the task compose file that does not set `network_mode` or `networks`, into that sidecar's network namespace (`network_mode: service:harbor-docker-egress-control-sidecar`).
See `_egress_controlled_service_names` and `_write_egress_control_services_compose_file` in `harbor/environments/docker/docker.py`.
The `[agent]` policy is switched on around the agent phase and switched back to the `[environment]` baseline afterwards (`_phase_network_policy` in `harbor/trial/trial.py`).

This means the plain compose file behaves differently from a compose file where the second service declares its network.
I ran both.

### Round 1: plain compose (no `networks:` on `server`)

| Variant | `[agent]` block | Result | Oracle output |
|---------|-----------------|--------|---------------|
| a | none | PASS, reward 1.0 (`jobs/2026-11-11__18-58-42`) | fetched the value |
| b | `network_mode = "allowlist"`, `allowed_hosts = ["api.anthropic.com"]` | FAIL, reward 0.0 | `FETCH FAILED for http://server:8000/value.txt: URLError: <urlopen error [Errno -2] Name or service not known>` |
| c | allowlist with `["api.anthropic.com", "server"]` | FAIL, reward 0.0 | same DNS error |
| d | `network_mode = "no-network"` | FAIL, reward 0.0 | same DNS error |

A diagnostic copy of the task showed why.
With both services inside the sidecar's namespace, `server` does not resolve, but `http://localhost:8000/value.txt` returns `200 b'sidecar-value-7341\n'`.
So in round 1, c fails because of the namespace topology, not because the allowlist blocked it.

### Round 2: `server` declares `networks: [default]` (the committed version)

```yaml
services:
  main:
    depends_on:
      - server
  server:
    build:
      context: ./server
    networks:
      - default
```

| Variant | Result | Job | Oracle output |
|---------|--------|-----|---------------|
| a default | PASS, reward 1 | `2026-11-11__19-05-02` | `FETCHED: 'sidecar-value-7341\n'` |
| b allowlist, anthropic only | FAIL, reward 0 | `2026-11-11__19-05-33` | `FETCH FAILED for http://server:8000/value.txt: RemoteDisconnected: Remote end closed connection without response` |
| c allowlist plus `server` | PASS, reward 1 | `2026-11-11__19-06-08` | `FETCHED: 'sidecar-value-7341\n'` |
| d no-network | FAIL, reward 0 | `2026-11-11__19-06-43` | `FETCH FAILED for http://server:8000/value.txt: RemoteDisconnected: Remote end closed connection without response` |

In b and d, `server` resolves (for example `172.18.0.3 server`) but the connection is cut by the egress proxy.
After round 2, I restored the task to the default `[agent]` block and ran it once more (`2026-11-11__19-07-18`, reward 1).
That is the state committed on the branch.

The diagnostic copy also checked outside hosts in the same setup:
- In c, `https://api.anthropic.com/` got through to a TLS handshake.
  It then failed with `CERTIFICATE_VERIFY_FAILED` because of this container's proxy CA.
  `https://example.com/` was cut with `UNEXPECTED_EOF_WHILE_READING`.
- In d, both were cut with `UNEXPECTED_EOF_WHILE_READING`.
- DNS lookups for outside names still succeed in every mode.
  Only connections are blocked.

### Does the `[agent]` network setting apply to the oracle?

Yes.
The policy is applied to the environment around whatever agent runs, and the oracle's `solve.sh` runs in `main`.
The b and d failures above were produced by the oracle.
The trial log for the restricted runs also says:

```
Agent 'oracle' exposes no native web search or fetch tools for Harbor to disable; continuing. Sandbox network policy still applies.
```

So this test is meaningful for the oracle.

### Notes for the real task

- If a sidecar must be reachable by name under `allowlist`, give that service an explicit `networks:` entry and add its service name to `allowed_hosts`.
- Otherwise, under any non-public mode, the agent reaches it only at `localhost:<port>`, and the allowlist does not seem to govern that traffic (round 1 showed `localhost` working in no-network mode).
- `harbor lint` on smoke-sidecar reports `[shared-verifier] Verifier shares the agent sandbox; set verifier.environment_mode = "separate"` (exit 1).
  I kept shared mode to keep the smoke test small.
  It ran fine, but it does not pass default lint.
- `harbor run --help` also lists `--allow-agent-host` ("Allow hostname or IP/CIDR during agent execution only").
  I did not test it.
- Not verified: whether `harbor lint` or any run notices that the egress sidecar cannot start on a host without nftables support.
  From code reading, Harbor probes the kernel, and if egress control is unavailable a non-public policy raises `Docker egress control was not enabled when the environment started, so it cannot enforce this network policy.`

## 7. Command forms (dry run only)

No `ANTHROPIC_API_KEY` was set, so nothing could have reached the API.
None of these created a `jobs/` entry.

1. `harbor run -p scratch/smoke-basic -a claude-code -m anthropic/claude-opus-5-5 --dry-run` exits 0:

```
Parsed provider     │ anthropic
Resolved model      │ claude-opus-5-5
Endpoint            │ https://api.anthropic.com
API format          │ anthropic_messages
No API key selected. Set ANTHROPIC_API_KEY or use --api-key-name.
Keys and model availability were not verified. Native login or other authentication may apply when no API key is found.
Dry run OK - 1 trial(s); nothing was run.
```

2. Adding `--effort high` exits 0 with the same table and `Dry run OK`.
   The table does not show effort.
   `--effort` is validated, though: `--effort bogus` fails with `Invalid kwargs for agent 'claude-code': reasoning_effort: Input should be 'low', 'medium', 'high', 'xhigh' or 'max'`.

3. `harbor run -p scratch/smoke-basic -a claude -m opus-5-5 --dry-run` exits 1:

```
Dry run failed: agents[0]: Agent name claude is not valid. Valid agent names:
{..., 'claude-code', ..., 'oracle', ...}
```

Extra forms I tried to separate the two changes:
- `-a claude-code -m opus-5-5` exits 0, but the resolved model is the literal `opus-5-5`.
  There is no alias expansion, so this would likely fail at the API.
  I did not verify that, because it would need a real call.
- `-a claude-code -m claude-opus-5-5` exits 0 with resolved model `claude-opus-5-5` and provider `anthropic`.

Accepted: `-a claude-code -m anthropic/claude-opus-5-5`, with or without `--effort high`.
Rejected: `-a claude`.
Note that a dry run does not check keys or whether the model exists.

## 8. Claude Code agent implementation (read-only)

File: `harbor/agents/installed/claude_code.py` (Harbor 0.25.0, 2233 lines).

### Install

`install()`, lines 635-659.
It skips the install if `claude` is already on PATH at the requested version.
Otherwise it installs `curl bash nodejs npm procps`, then uses the native bootstrap script (npm only on Alpine):

```python
await self.ensure_system_dependencies(
    environment, ("curl", "bash", "nodejs", "npm", "procps")
)
...
"if command -v apk &> /dev/null; then"
f"  npm install -g @anthropic-ai/claude-code{'@' + self._version if self._version else ''};"
" else"
f"  curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash -s --{version_flag};"
" fi && "
```

So the agent container needs outbound access to `downloads.claude.ai` (or npm on Alpine) during setup, unless Claude Code is preinstalled in the image.
From code reading, the `[agent]` phase policy only wraps the run step, so an `[agent]` allowlist should not block the install.
An `[environment]` level `no-network` would block it.
I did not verify this with a run.

### Launch command

`run()`, lines 2206-2220.
The instruction is passed as the prompt on stdin, through an env var, not written to a file:

```python
instruction_shell_var = f"claude_code_instruction_{uuid.uuid4().hex}"
instruction_env_var = instruction_shell_var.upper()
run_env = {**env, instruction_env_var: instruction}
...
f'{instruction_shell_var}="${instruction_env_var}"; '
f"unset {instruction_env_var}; "
f'printf "%s" "${instruction_shell_var}" | '
f"claude --verbose --output-format=stream-json "
f"{settings_flag}"
f"{extra_flags}"
f"{resume_flag}"
f"--print 2>&1 | tee "
f"{(self.environment_logs_dir / 'claude-code.txt').as_posix()}"
```

The instruction goes through `render_instruction` first, which only changes it if a prompt template path is configured (`harbor/agents/installed/base.py:1110`).

### Flags

From `ClaudeCodeOptions`, lines 60-115, rendered by `build_cli_flags()`:

- `--permission-mode=bypassPermissions` (default value of `permission_mode`)
- `--effort <level>` from `--effort` / `reasoning_effort`, falling back to `CLAUDE_CODE_EFFORT_LEVEL`
- `--max-turns` (fallback `CLAUDE_CODE_MAX_TURNS`), `--thinking-display`, `--max-budget-usd`, `--fallback-model`, `--append-system-prompt`, `--allowedTools`, `--disallowedTools`, only when set
- `--settings /tmp/claude-code-settings/settings.json` only when a config source is given
- `--continue` or `--resume <id>` only for resume or load
- `MAX_THINKING_TOKENS` is passed as an env var when set

### Environment variables

From `run()`, lines 2123-2152:

```python
env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = max_output_tokens   # only if set on the host
env["ANTHROPIC_MODEL"] = resolved_model
if "ANTHROPIC_BASE_URL" in env and "ANTHROPIC_MODEL" in env:
    env.update(self._model_alias_env(env["ANTHROPIC_MODEL"], all_aliases=True))
if os.environ.get("CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING", "").strip() == "1":
    env["CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING"] = "1"
env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
env["IS_SANDBOX"] = "1"
env.update(self._resolved_env_vars)
env["CLAUDE_CONFIG_DIR"] = (self.environment_logs_dir / "sessions").as_posix()
```

Auth comes from `_resolve_auth_env()`: `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `CLAUDE_CODE_OAUTH_TOKEN`, or `ANTHROPIC_AUTH_TOKEN` for gateways, plus Bedrock variables when Bedrock is used.
`_model_alias_env` sets `ANTHROPIC_DEFAULT_{SONNET,OPUS,HAIKU,FABLE}_MODEL` and `CLAUDE_CODE_SUBAGENT_MODEL` to the chosen model unless you set them yourself.
That happens whenever `ANTHROPIC_BASE_URL` ends up in the env, which the dry run shows is the case here (the ambient value was selected).
So subagents would also run on the chosen model.

### Context window and auto-compact

Nothing.
A grep of the whole installed Harbor package for `1M_CONTEXT`, `[1m]`, `AUTOCOMPACT`, `AUTO_COMPACT`, `autoCompact`, `context-1m` and `CONTEXT_WINDOW` finds no match in the Claude Code agent.
The only `context_window` hits are in `agents/installed/mcode.py`, a different agent.
Harbor does not set `CLAUDE_CODE_DISABLE_1M_CONTEXT` or any auto-compact setting.
Claude Code's own defaults apply unless you pass them yourself, for example with `--ae CLAUDE_CODE_DISABLE_1M_CONTEXT=1` or a settings file.
I did not check how `--ae` is forwarded at runtime.

### Web tools under restricted network modes

Yes, they are disabled automatically.
`ClaudeCode.capabilities` has `native_web_tools=True` (line 122).
At the start of the agent phase, `trial.py:692` calls:

```python
async def _configure_web_tools(self, policy: NetworkPolicy) -> None:
    disabled = policy.network_mode != NetworkMode.PUBLIC
    await self.agent.set_web_tools_disabled(disabled, self.agent_environment)
```

`agents/base.py:197-246` then re-parses the options with `disable_web_search=True`, unless you passed `disable_web_search` yourself.
`ClaudeCodeOptions._disallow_web_tools` (lines 89-94) turns that into a flag:

```python
if self.disable_web_search:
    tools = [self.disallowed_tools] if self.disallowed_tools else []
    self.disallowed_tools = ",".join([*tools, "WebSearch", "WebFetch"])
```

So under `allowlist` or `no-network`, Claude Code is launched with `--disallowedTools WebSearch,WebFetch`, plus anything you added.
This is from code reading only, because no real Claude Code run was made.

## Not verified in this session

- hello-world scoring 1.0 (blocked by this container's TLS proxy).
- Any real `claude-code` run, including whether `--effort high` and the env vars above reach the CLI as described.
- Whether `-m opus-5-5` would be rejected by the API.
- `--allow-agent-host`.
- Claude Code install under `[environment] network_mode = "no-network"`.
- The smoke-sidecar task with a separate verifier.

## Repeat on your laptop

```bash
# prerequisites: Docker running, uv installed
docker info
uv tool install harbor
harbor --version

# 3. hello world
harbor run -t hello-world/hello-world -a oracle

# 4 and 5. basic task
harbor lint scratch/smoke-basic
harbor lint --select ALL scratch/smoke-basic
harbor run -p scratch/smoke-basic -a oracle
cat jobs/*/smoke-basic__*/verifier/reward.json

# 6. sidecar: run once per variant, editing the [agent] block of
#    scratch/smoke-sidecar/task.toml between runs
#    a: (nothing)
#    b: network_mode = "allowlist" / allowed_hosts = ["api.anthropic.com"]
#    c: network_mode = "allowlist" / allowed_hosts = ["api.anthropic.com", "server"]
#    d: network_mode = "no-network"
harbor run -p scratch/smoke-sidecar -a oracle
cat jobs/$(ls -t jobs | head -1)/*/agent/oracle.txt
#    to reproduce round 1, delete the "networks:" block for server in
#    scratch/smoke-sidecar/environment/docker-compose.yaml

# 7. dry runs (no credits used)
harbor run -p scratch/smoke-basic -a claude-code -m anthropic/claude-opus-5-5 --dry-run
harbor run -p scratch/smoke-basic -a claude-code -m anthropic/claude-opus-5-5 --effort high --dry-run
harbor run -p scratch/smoke-basic -a claude -m opus-5-5 --dry-run

# 8. find the Claude Code agent source
less "$(uv tool dir)/harbor/lib/python3.*/site-packages/harbor/agents/installed/claude_code.py"
```
