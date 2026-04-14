# Autonomous Incident Response Benchmark

Most AI agent demos out there feel like glorified text games: the agent guesses a command, the system checks if it matches a string, and everyone claps. I built this project because I wanted a benchmark that genuinely tests an agent's ability to troubleshoot an infrastructure incident under pressure, without hardcoded rails. 

This isn't a sandbox where an LLM can just freestyle bash commands. It’s a multi-agent system (Planner + Executor) running in a deterministic environment that forces the AI to reason through noise, recover from its own bad decisions, and actually "learn" from previous executions.

It’s an evaluation platform meant for benchmarking real DevOps AI capabilities.

## How It Works

At its core, this is a simulated control plane where the AI acts as an SRE. 

1. **The Generator (`tasks.py`)**: Before each run, the environment dynamically spins up a parameterized incident (e.g., API CPU Spike vs. DB CPU Spike). It injects intentionally misleading signals into the pager alert—like a responder in the Slack channel falsely claiming it's a memory leak.
2. **The Planner loop**: The Planner agent receives the incident and long-term memory patterns. It has to output a strict JSON strategy with exactly what it intends to do.
3. **The Executor block**: The Executor is basically a gatekeeper. It reads the Planner's JSON and cross-references it with the history. If the Planner suggests something that already failed, the Executor rejects it and fires a `REPLAN` command back up the chain.
4. **The Environment**: The environment evaluates the token, handles the reward logic, increments the state, and records the history.
5. **Scoring (`grader.py`)**: You don't just get a 1.0 for eventually fixing the problem. Taking unnecessary actions docks your score. Repeating a failed action docks your score heavily. Getting distracted by the decoy text in the prompt kills your efficiency multiplier.

## Key Design Decisions

I went through a few iterations before landing on this architecture. Here's why it's built this way:

* **Separating the Planner and Executor**: Initially, I just had one agent generating the "reasoning" and the "token" at once. It failed constantly. LLMs struggle to reason and conform to strict output tokens in the same breath. Splitting them meant the Planner could think deeply in JSON, and the Executor could enforce pure logic mapping.
* **Executor Validation**: The Executor has veto power. If the Planner decides to blindly follow the runbook and tries to `scale_out_api` when the issue is database exhaustion, the environment flags it as a failure. On the next loop, if the Planner stubbornly suggests it again, the Executor catches the logic gap, refuses to execute, and triggers a `REPLAN`. It's a self-correcting feedback loop.
* **Adversarial Noise**: Real incidents are messy. People panic and suggest wrong fixes in incident channels. I hardcoded this noise directly into the task generation to ensure the agent is actually diagnosing the problem, not just extracting keywords and pattern matching. 
* **Strict Scoring**: The score had to mean something. It clamps strictly between `(0, 1)`. Decision quality penalties take chunks off the final raw score right at the end to punish guessing.

## What Makes This Interesting

* **Handling Misleading Signals**: It proves the agent relies on the actual allowed playbooks and metric logic, rather than blindly summarizing the prompt text.
* **Failure to Recovery**: Because the Executor gates bad actions and feeds failures back to the Planner, you can watch the system try a decoy solution, fail, recognize why it failed, and dynamically shift to the correct mitigation path without blowing up the loop.
* **Abstract Pattern Memory**: The memory system doesn't save the exact token sequence (that's just cheating). It abstracts successful paths into patterns (e.g., `diagnose -> investigate -> mitigate`). The agent has to deduce how that pattern applies to a completely new context on the next run.

## Project Structure

* `inference.py` - The main loop where all the magic happens. Houses the JSON planner, the Executor gate, and the memory read/writes.
* `env.py` - The deterministic state machine representing the infrastructure. Handles the step logic and progress ratio.
* `grader.py` - The harsh judge. Calculates the multi-factor punitive score (Correctness, Efficiency, Stability, and Decision Quality).
* `tasks.py` - The dynamic factory that builds the runbooks and injects the adversarial noise on the fly.

## How to Run

You need your OpenAI credentials exported natively. 

```bash
export API_KEY="your-api-key"
export API_BASE_URL="https://api.openai.com/v1"

# Run the benchmark suite
python inference.py
```

## Limitations

As much as I've polished this, it's still a prototype with some glaring gaps:
* **Tight Rails**: Setting up a truly open-ended environment is hard. While the tasks are dynamically generated, the underlying correct path is still mathematically deterministic at the environment level. It doesn't actually 'execute' terraform or bash scripts.
* **Basic Memory**: The `LongTermMemory` module is basically a JSON file caching abstracted string sequences. It works, but a proper vector DB storing incident vectors would make the pattern matching far more robust in a massive playbook scenario.
* **Reasoning Score**: The 10% weight for "Reasoning" in `grader.py` is currently just a placeholder scalar of `1.0`. Right now, decision quality is mostly enforced through punitive subtractions instead of a dedicated LLM-as-a-judge reasoning score.

## Future Improvements

* Add a persistence layer (like SQLite) for memory instead of `agent_memory.json` to handle concurrency and thousands of runs.
* Connect the execution tokens to a real sandbox (like a docker container mapped to `subprocess`) where the commands actually mutate real state, shifting the evaluation from a deterministic graph to actual sandbox assertions.
