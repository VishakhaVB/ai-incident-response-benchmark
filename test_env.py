from __future__ import annotations

from typing import Any

from env import RunbookEnv
from tasks import Task, get_task, list_tasks

INVALID_ACTION = "ACTION_NOT_ALLOWED"
DEBUG_LOG_STEPS = True


def log_step(step: int, action: str, reward: float, progress: float, done: bool) -> None:
	print(
		f"Step: {step} | Action: {action} | Reward: {reward:.3f} | "
		f"Progress: {progress:.3f} | Done: {done}"
	)


def _get_easy_task() -> Task:
	easy_task = next(task for task in list_tasks() if task.difficulty == "easy")
	return get_task(easy_task.id)


def _run_actions(env: RunbookEnv, actions: list[str], debug: bool = DEBUG_LOG_STEPS) -> list[dict[str, Any]]:
	results: list[dict[str, Any]] = []
	for action in actions:
		if env.done:
			break
		observation, reward, done, _info = env.step(action)
		if debug:
			log_step(
				step=observation["current_step"],
				action=action,
				reward=float(reward),
				progress=float(observation["progress_ratio"]),
				done=bool(done),
			)
		results.append(
			{
				"action": action,
				"reward": reward,
				"done": done,
				"progress_ratio": observation["progress_ratio"],
			}
		)
	return results


def _print_test_result(
	test_name: str,
	actions: list[str],
	state: dict[str, Any],
	checks: dict[str, bool],
	results: list[dict[str, Any]],
	status: str,
) -> None:
	print(f"=== {test_name} ===")
	print(f"actions_taken: {actions}")
	print(f"executed_steps: {len(results)}")
	print(f"final_state: {state}")
	print(
		"summary: "
		f"{state['correct_steps_count']} correct / {state['wrong_steps_count']} wrong"
	)
	for check_name, passed in checks.items():
		print(f"check_{check_name}: {'PASS' if passed else 'FAIL'}")
	print(f"result: {status}")
	print()


def test_correct_path() -> bool:
	task = _get_easy_task()
	env = RunbookEnv(task)
	env.reset()

	actions = list(task.steps)
	results = _run_actions(env=env, actions=actions)
	state = env.state()

	checks = {
		"done_true": state["done"] is True,
		"progress_complete": state["progress_ratio"] == 1.0,
		"wrong_steps_zero": state["wrong_steps_count"] == 0,
	}
	passed = all(checks.values())

	_print_test_result(
		"Test Case 1: Correct Path",
		actions,
		state,
		checks,
		results,
		"PASS" if passed else "FAIL",
	)
	return passed


def test_wrong_actions() -> bool:
	task = _get_easy_task()
	env = RunbookEnv(task)
	env.reset()

	actions = [
		task.steps[1],
		task.steps[0],
		task.steps[2],
	]
	results = _run_actions(env=env, actions=actions)
	state = env.state()

	negative_rewards = [result["reward"] for result in results if result["reward"] < 0.0]
	checks = {
		"negative_reward_present": len(negative_rewards) > 0,
		"wrong_steps_increased": state["wrong_steps_count"] > 0,
		"stable_state": state["current_step_index"] <= state["total_steps"],
	}
	passed = all(checks.values())

	_print_test_result(
		"Test Case 2: Wrong Action Handling",
		actions,
		state,
		checks,
		results,
		"PASS" if passed else "FAIL",
	)
	return passed


def test_invalid_action() -> bool:
	task = _get_easy_task()
	env = RunbookEnv(task)
	env.reset()

	actions = [INVALID_ACTION, task.steps[0]]
	results = _run_actions(env=env, actions=actions)
	state = env.state()

	invalid_reward = results[0]["reward"] if results else 0.0
	checks = {
		"strong_penalty": invalid_reward <= -1.0,
		"state_stable": state["current_step_index"] >= 0,
		"continued_safely": len(state["history"]) >= 1,
	}
	passed = all(checks.values())

	_print_test_result(
		"Test Case 3: Invalid Action",
		actions,
		state,
		checks,
		results,
		"PASS" if passed else "FAIL",
	)
	return passed


def test_edge_cases() -> bool:
	task = _get_easy_task()

	empty_env = RunbookEnv(task)
	empty_env.reset()
	empty_actions: list[str] = []
	empty_results = _run_actions(env=empty_env, actions=empty_actions)
	empty_state = empty_env.state()

	long_env = RunbookEnv(task)
	long_env.reset()
	long_actions = task.steps + [task.steps[0], INVALID_ACTION]
	long_results = _run_actions(env=long_env, actions=long_actions)
	long_state = long_env.state()

	repeat_env = RunbookEnv(task)
	repeat_env.reset()
	repeat_actions = [task.steps[1], task.steps[1], task.steps[1], task.steps[0]]
	repeat_results = _run_actions(env=repeat_env, actions=repeat_actions)
	repeat_state = repeat_env.state()

	empty_checks = {
		"no_crash": True,
		"no_index_errors": empty_state["current_step_index"] == 0,
		"done_logic_valid": empty_state["done"] is False,
	}
	empty_passed = all(empty_checks.values())
	_print_test_result(
		"Test Case 4A: Edge - Empty Action List",
		empty_actions,
		empty_state,
		empty_checks,
		empty_results,
		"PASS" if empty_passed else "FAIL",
	)

	long_checks = {
		"no_crash": True,
		"no_index_errors": long_state["current_step_index"] <= long_state["total_steps"],
		"done_logic_valid": long_state["done"] is True,
	}
	long_passed = all(long_checks.values())
	_print_test_result(
		"Test Case 4B: Edge - Actions Longer Than Required",
		long_actions,
		long_state,
		long_checks,
		long_results,
		"PASS" if long_passed else "FAIL",
	)

	repeat_checks = {
		"no_crash": True,
		"no_index_errors": repeat_state["current_step_index"] <= repeat_state["total_steps"],
		"wrong_steps_increased": repeat_state["wrong_steps_count"] > 0,
	}
	repeat_passed = all(repeat_checks.values())
	_print_test_result(
		"Test Case 4C: Edge - Repeated Wrong Action",
		repeat_actions,
		repeat_state,
		repeat_checks,
		repeat_results,
		"PASS" if repeat_passed else "FAIL",
	)

	return empty_passed and long_passed and repeat_passed


def run_all_tests() -> None:
	print("RunbookEnv Manual Test Suite")
	print()
	test_results: list[tuple[str, bool]] = []

	test_results.append(("Test Case 1: Correct Path", test_correct_path()))
	test_results.append(("Test Case 2: Wrong Action Handling", test_wrong_actions()))
	test_results.append(("Test Case 3: Invalid Action", test_invalid_action()))
	test_results.append(("Test Case 4: Edge Cases", test_edge_cases()))

	passed_count = sum(1 for _name, passed in test_results if passed)
	failed_count = len(test_results) - passed_count

	print("=== Test Summary ===")
	for name, passed in test_results:
		print(f"{name}: {'PASS' if passed else 'FAIL'}")
	print(f"passed: {passed_count}")
	print(f"failed: {failed_count}")


def main() -> None:
	run_all_tests()


if __name__ == "__main__":
	main()
