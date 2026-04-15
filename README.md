# Autonomous Incident Response Benchmark

Production-grade benchmark for evaluating whether AI responders can make correct operational decisions under incident pressure.

If your AI agent only succeeds when the prompt is clean and the path is obvious, it will fail at 3:07 AM during a real incident.

This benchmark is built to test whether an agent can behave like a credible on-call SRE under pressure: noisy alerts, misleading signals, partial context, and penalties for bad judgment. It is not a command-matching toy and it is not a prompt-game leaderboard hack.

The system runs a strict Planner + Executor architecture against a deterministic runbook environment, then scores outcome quality with explicit penalties for wasted or repeated actions.

## TL;DR

- Multi-agent incident response benchmark with strict Planner + Executor control.
- Dynamic tasks include adversarial noise to test real diagnostic discipline.
- `REPLAN` gating blocks repeated or logically bad actions.
- Scoring rewards correctness and punishes waste, repetition, and low-quality decisions.
- Built to measure operational reliability, not prompt fluency.

## Why This Matters in Production

Teams are already wiring LLM agents into ops workflows: triage bots, runbook copilots, auto-remediation pipelines. Most evaluations today still answer the wrong question: "Can the model produce a plausible response?"

This project answers the harder one: "Can the system consistently make good operational decisions when the context is adversarial?"

Real-world relevance:

- It tests resilience to bad human input (for example: confident but wrong guidance in incident chat).
- It penalizes brute-force behavior that would be expensive or dangerous in production.
- It surfaces whether an agent can recover from failure instead of repeating it.
- It evaluates decision quality, not just final task completion.

## System Overview

At runtime, the benchmark simulates a control plane where the agent acts as the responder.

1. **Dynamic incident generation (`tasks.py`)**
   Each episode is parameterized (CPU spike, DB exhaustion, regional outage) and injected with decoy signals.

2. **Planner (`inference.py`)**
   The Planner receives observation + prior failures + long-term strategy patterns and must produce strict JSON:
   ```json
   {
     "plan": ["action_1", "action_2", "action_3"],
     "current_focus": "action_1"
   }
   ```

3. **Executor gate (`inference.py`)**
   The Executor validates `current_focus` against action history and logic constraints. If invalid or repetitive, it returns `REPLAN`.

4. **Environment transition (`env.py`)**
   The environment applies the selected token, advances or blocks progress, and records history.

5. **Scoring (`grader.py`)**
   Final score is clamped to `(0, 1)` and reduced by efficiency and decision-quality penalties.

## Architecture Decisions (Opinionated, On Purpose)

- **Planner and Executor are split intentionally.** One model trying to reason and emit final action tokens in a single pass fails too often. Separating cognition from execution validation materially improves reliability.

- **Executor veto is non-negotiable.** If a proposed action already failed, the system does not "hope for better wording". It rejects and replans.

- **Adversarial noise is first-class.** Incident channels are noisy in real life. Evaluations without misinformation resistance are not serious.

- **Memory stores abstractions, not token transcripts.** Successful episodes are compressed into patterns like `diagnose -> investigate -> mitigate`, avoiding direct path memorization.

## Example Execution Walkthrough

Below is a typical run shape for a DB exhaustion scenario with misleading context.

### Episode Setup

- Incident text includes a real DB pool bottleneck.
- Decoy text suggests scaling API replicas first.
- Allowed actions include both relevant and irrelevant tokens.

### Loop Behavior

1. Planner proposes: `inspect_db_metrics -> scale_out_api -> raise_pool_size`
2. Executor accepts `inspect_db_metrics`.
3. Planner focus shifts to `scale_out_api`.
4. Environment marks no meaningful progress on that step.
5. Executor detects failed logic repetition and emits `REPLAN`.
6. Planner revises path: `identify_long_queries -> kill_long_query -> raise_pool_size`
7. Environment progresses to resolution.

### What the score captures

- Correct mitigation sequence eventually found.
- Penalty applied for the early decoy action.
- Bigger penalty if the same failed action is repeated.

This is exactly the behavior you want to inspect before putting an autonomous responder anywhere near production change authority.

## Proof Signals You Can Measure

This benchmark is useful because it produces inspectable operational signals, not just pass/fail status:

- **Recovery quality**: How quickly does the agent pivot after a failed hypothesis?
- **Efficiency**: How many unnecessary steps were taken before resolution?
- **Stability**: Does the policy remain coherent across mixed incident types?
- **Decision discipline**: Does it avoid retrying known-bad actions?

## Architecture

Diagram placeholder (replace with your actual system diagram):

```text
+---------------------+       +--------------------+
| Incident Generator  | ----> |      Planner       |
|      (tasks.py)     |       |   (JSON strategy)  |
+---------------------+       +--------------------+
                 |
                 v
              +--------------------+
              | Executor Action    |
              | Gate (`REPLAN`)    |
              +--------------------+
                 |
                 v
+---------------------+       +--------------------+
|   Grader            | <---- | Environment        |
|   (penalty-aware)   |       | (state transition) |
+---------------------+       +--------------------+
                 |
                 v
              +--------------------+
              | Long-Term Memory   |
              | pattern abstraction|
              +--------------------+
```

## Repository Layout

- `inference.py`: Main orchestration loop, Planner/Executor coordination, long-term memory read/write.
- `env.py`: Deterministic state machine, step transitions, and progress accounting.
- `tasks.py`: Dynamic incident factory + adversarial signal injection.
- `grader.py`: Multi-factor scoring with punitive decision-quality deductions.
- `test_env.py`: Behavioral checks for correctness path, invalid actions, and edge cases.

## Run Locally

### 1) Install dependencies

```bash
pip install -e .
```

### 2) Configure credentials

`inference.py` requires both environment variables:

```bash
export API_KEY="your-api-key"
export API_BASE_URL="https://api.openai.com/v1"
```

PowerShell equivalent:

```powershell
$env:API_KEY = "your-api-key"
$env:API_BASE_URL = "https://api.openai.com/v1"
```

### 3) Execute benchmark suite

```bash
python inference.py
```

The run executes all generated tasks and prints per-task score plus overall average.

## Current Limits

This is intentionally rigorous, but still a prototype in a few areas:

- **Deterministic action graph** Tasks are dynamic, but valid resolution paths are still constrained by environment logic.

- **Simple persistence layer** `agent_memory.json` works for local experimentation but is not ideal for high-volume concurrent evaluations.

- **Reasoning component in scoring is lightweight** Decision quality is enforced primarily through explicit penalties rather than a deep reasoning judge.

## Example Result

Representative console output from a benchmark run:

```text
--- Starting Elite Multi-Agent Inference for Task: db_exhaustion_2f19a3b1 ---
Step: 1 | Action: inspect_db_metrics (Inspect application metrics for active DB connections versus configured pool size) | Reward: 0.40 | Progress: 0.25
Step: 2 | Action: scale_out_api (Scale out API replicas by one and verify latency recovers) | Reward: -0.50 | Progress: 0.25
--- Executor triggered REPLAN. Reconstructing strategy. ---
Step: 3 | Action: identify_long_queries (Identify long-running queries from database monitoring and capture offending endpoints) | Reward: 0.30 | Progress: 0.50
Step: 4 | Action: kill_long_query (Terminate the identified blocking query in the database) | Reward: 0.35 | Progress: 0.75
Step: 5 | Action: raise_pool_size (Temporarily raise connection pool size within safe database limits) | Reward: 0.45 | Progress: 1.00

--- Final Score for Task 'db_exhaustion_2f19a3b1' ---
Score: 0.87 (87.0%)
Correct Matches: 3 / 3
Penalties Assessed (Decision Quality): -0.13

==================================================
=== OVERALL AVERAGE SCORE: 0.81 ===
==================================================
```

## Vision

The goal is to evolve this from a deterministic benchmark into a high-fidelity agent reliability harness for real ops teams.

Next upgrades:

- Move memory persistence to SQLite (or a vector-backed store) for scale and richer retrieval.
- Attach action tokens to a constrained execution sandbox so state transitions are validated against real side effects.
- Expand scoring with stronger reasoning-quality evaluation while keeping punitive operational metrics.

If your team is evaluating autonomous incident response, this project is built to answer the uncomfortable but useful question: not whether the agent can talk like an SRE, but whether it can actually act like one.

When an incident escalates, fluent language is irrelevant. Correct actions under uncertainty are what count, and this benchmark is designed to measure exactly that.
