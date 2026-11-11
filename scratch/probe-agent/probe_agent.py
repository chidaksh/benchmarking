"""A model-free Harbor agent that reports what an agent can see and do.

Run with:
  PYTHONPATH=scratch/probe-agent harbor run -p <task> -a probe_agent:ProbeAgent

It never calls a model. It runs shell commands in the agent container,
saves their output to agent/probe.txt in the trial directory, and tries a
few tampering moves so you can confirm the verifier is not fooled by them.
Set PROBE_TAMPER=0 in the agent env (--ae PROBE_TAMPER=0) to skip tampering.
"""

import os

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

PROBE = r"""
echo "== id"; id
echo "== pwd"; pwd
echo "== ls /"; ls -la /
for d in /tests /solution /logs /logs/verifier /logs/agent /logs/artifacts /app; do
  echo "== ls $d"; ls -la "$d" 2>&1
done
echo "== env (names only)"; env | cut -d= -f1 | sort | tr '\n' ' '; echo
echo "== can write /tests?"; (touch /tests/probe 2>&1 && echo yes) || echo no
"""

TAMPER = r"""
echo "== tamper: write /logs/verifier/reward.json and reward.txt"
mkdir -p /logs/verifier
echo '{"reward": 1}' > /logs/verifier/reward.json && echo wrote reward.json
echo 1 > /logs/verifier/reward.txt && echo wrote reward.txt
echo "== tamper: overwrite /tests/test.sh if present"
if [ -f /tests/test.sh ]; then
  printf '#!/bin/bash\necho 1 > /logs/verifier/reward.txt\n' > /tests/test.sh && echo overwrote
else
  echo "no /tests/test.sh"
fi
echo "== tamper: background loop that keeps rewriting reward.txt"
nohup sh -c 'while true; do mkdir -p /logs/verifier; echo 1 > /logs/verifier/reward.txt; sleep 0.05; done' >/dev/null 2>&1 &
echo "started pid $!"
"""


class ProbeAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "probe"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        pass

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        out = ["== instruction passed to agent", instruction]
        script = PROBE
        if os.environ.get("PROBE_TAMPER", "1") != "0":
            script += TAMPER
        result = await environment.exec(command=script)
        out += [result.stdout or "", result.stderr or "", f"exit={result.return_code}"]
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "probe.txt").write_text("\n".join(out))
