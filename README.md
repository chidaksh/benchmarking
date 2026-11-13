# Harbor task

This repository holds one agent task in [Harbor](https://docs.harborframework.com/) format, under `task-draft/`.
`task-draft/` is a placeholder used to confirm the setup and will be replaced by the real task.

## Requirements

- Docker, running.
- [uv](https://docs.astral.sh/uv/).
- An Anthropic API key, for runs that call a model.

## Install Harbor

```bash
uv tool install harbor==0.25.0
harbor --version
```

## Run the task

Run all commands from the repository root.

Reference solution:

```bash
harbor run -p task-draft -a oracle
```

Claude Code with Opus 5.5:

```bash
export ANTHROPIC_API_KEY=<your key>
harbor run -p task-draft -a claude-code -m anthropic/claude-opus-5-5 --effort high --ak version=2.1.322
```

`--ak version=2.1.322` pins the Claude Code release that Harbor installs in the container.
Each run writes its logs, the agent trajectory and the score to `jobs/`.

## View results

```bash
harbor view jobs
```

This serves the runs in `jobs/` at http://127.0.0.1:8080.

On the `taxcalcbench-trial` branch, `jobs/` holds only the Claude Code with Opus 5.5 runs listed in `taxcalcbench-trial/README.md`.
