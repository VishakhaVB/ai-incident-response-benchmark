from __future__ import annotations

from typing import Any


def _build_mistakes(actions: list[str], correct_steps: list[str]) -> list[dict[str, Any]]:
	mistakes: list[dict[str, Any]] = []
	comparison_length = min(len(actions), len(correct_steps))

	for index in range(comparison_length):
		expected = correct_steps[index]
		actual = actions[index]
		if actual != expected:
			mistakes.append({"index": index, "expected": expected, "actual": actual})

	for index in range(comparison_length, len(correct_steps)):
		mistakes.append({"index": index, "expected": correct_steps[index], "actual": None})

	return mistakes


def grade(actions: list[str], correct_steps: list[str]) -> dict[str, Any]:
	total_steps: int = len(correct_steps)
	comparison_length: int = min(len(actions), total_steps)

	correct_matches: int = 0
	incorrect_matches: int = 0

	for index in range(comparison_length):
		if actions[index] == correct_steps[index]:
			correct_matches += 1
		else:
			incorrect_matches += 1

	incorrect_matches += total_steps - comparison_length

	# 1. Correctness (50%)
	if total_steps == 0:
		cc_score: float = 1.0
	else:
		cc_score = float(correct_matches) / float(total_steps)
		
	# 2. Efficiency (20%) - fewer steps yields higher score
	if total_steps == 0:
		eff_score: float = 1.0 if not actions else 0.0
	else:
		eff_score = float(total_steps) / float(max(len(actions), total_steps))
		
	# 3. Stability (20%) - penalize repeated adjacent wrong actions
	repeated_mistakes: int = 0
	for i in range(1, len(actions)):
		if actions[i] == actions[i-1]:
			is_mistake = (i >= len(correct_steps)) or (actions[i] != correct_steps[i])
			if is_mistake:
				repeated_mistakes += 1
	stab_score: float = max(0.0, 1.0 - (float(repeated_mistakes) * 0.3))
	
	# 4. Reasoning Placeholder (10%)
	rsn_score: float = 1.0
	
	raw_score: float = (cc_score * 0.5) + (eff_score * 0.2) + (stab_score * 0.2) + (rsn_score * 0.1)

	# 5. Elite Grading: Explicit Decision Quality Penalties
	total_penalty: float = 0.0
	seen_actions: set[str] = set()
	for i, action in enumerate(actions):
		# Unnecessary step penalty (action not in correct_steps at all)
		if action not in correct_steps:
			total_penalty += 0.1
			
		# Penalty for repeating an action non-sequentially if it's already recorded as seen
		if action in seen_actions and (i >= len(correct_steps) or actions[i] != correct_steps[i]):
			total_penalty += 0.2
			
		seen_actions.add(action)

	penalized_score = max(0.0, raw_score - total_penalty)

	epsilon = 1e-6
	score = max(epsilon, min(1.0 - epsilon, float(penalized_score)))

	accuracy_percentage = score * 100.0
	mistakes = _build_mistakes(actions=actions, correct_steps=correct_steps)

	return {
		"score": score,
		"correct_steps_count": correct_matches,
		"total_steps": total_steps,
		"total_penalty": total_penalty,
		"accuracy_percentage": accuracy_percentage,
		"correct_matches": correct_matches,
		"incorrect_matches": incorrect_matches,
		"mistakes": mistakes,
		"components": {
			"correctness": cc_score,
			"efficiency": eff_score,
			"stability": stab_score,
			"reasoning": rsn_score
		}
	}
