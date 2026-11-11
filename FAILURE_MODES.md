# Failure modes

## Candidate failure modes

- Custom thing documented in an image: the task depends on something custom (a function, a format, a convention) that differs from the common version the model knows from training.
  Its real definition is in the documentation as an image, with little text describing it.
  The agent reads only the text, never sees the definition, and uses the common version.
- Compounding from an early step that looked successful: in a long task, an early step reaches its subgoal, but the way it was done is flawed.
  Nothing fails at that point, each later step builds on the flawed state, and the error grows until a later step fails or the final result is wrong.
  Example: a robot picks the orange, but with a grip that makes carrying and dropping it go wrong.
- State lost across long context: after compaction, the agent loses or misremembers facts that were held only in the conversation, such as earlier tool outputs.
- Clean exit taken as correct: a tool run finishes without error but its result is wrong, and the agent uses the result without checking it.

## Potential failure modes, to be confirmed

- Claims without evidence: the agent reports a result it never confirmed, or declares the task complete after a command was rejected or a required artifact is missing.
- Stopping at the first answer: the task needs every instance found or every alternative ruled out, and the agent stops after finding one.
- Spending before screening: with a limited budget of costly actions, the agent uses expensive ones before cheap ones have narrowed the options, and runs out before confirming an answer.
- Dismissing its own doubts: the agent notices something that does not fit, then explains it away or abandons its stated plan instead of investigating.
- Missed requirement: the task states several requirements, and the agent meets most of them and misses one.
