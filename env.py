from __future__ import annotations
from copy import deepcopy
from typing import Any
from tasks import Task, ACTION_MAP


class RunbookEnv:
	def __init__(self, task: Task) -> None:
		self.task: Task = task
		self.total_steps: int = len(task.steps)
		self.max_wrong_steps: int = 3

		self.current_step_index: int = 0
		self.done: bool = False
		self.history: list[tuple[str, str]] = []
		self.correct_steps_count: int = 0
		self.wrong_steps_count: int = 0
		self.last_action_reason: str = "N/A"

	def reset(self) -> dict[str, Any]:
		self.current_step_index = 0
		self.done = False
		self.history = []
		self.correct_steps_count = 0
		self.wrong_steps_count = 0
		self.last_action_reason = "N/A"

		return self._build_observation(last_action=None)

	def _get_incident_state(self) -> str:
		if self.current_step_index == 0:
			return "Issue detected. System awaiting diagnosis."
		elif self.current_step_index < self.total_steps:
			return f"Mitigation in progress. Step {self.current_step_index} completed."
		else:
			return "System stabilized after mitigation."

	def step(self, action: str, reason: str = "N/A") -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
		if self.done:
			observation = self._build_observation(last_action=action)
			info = self._build_info()
			return observation, 0.0, True, info

		self.history.append((action, reason))
		self.last_action_reason = reason
		reward: float = 0.0
		is_valid_action = action in self.task.allowed_actions
		is_correct = False

		if not is_valid_action:
			self.wrong_steps_count += 1
			reward = -1.0
		else:
			expected_action = self.task.steps[self.current_step_index]
			if action == expected_action:
				is_correct = True
				self.correct_steps_count += 1
				self.current_step_index += 1
				progress_ratio = (
					self.current_step_index / self.total_steps if self.total_steps else 0.0
				)
				reward = 0.2 + (0.6 * progress_ratio)
			else:
				self.wrong_steps_count += 1
				reward = -0.4

		if self.wrong_steps_count >= self.max_wrong_steps:
			self.done = True
			reward -= 0.5

		if self.current_step_index >= self.total_steps:
			self.done = True
		elif len(self.history) >= self.task.max_steps:
			self.done = True

		if is_correct and self.done and self.current_step_index >= self.total_steps and self.wrong_steps_count < self.max_wrong_steps:
			reward += 0.5

		reward = float(max(-1.0, min(1.0, reward)))

		observation = self._build_observation(last_action=action)
		info = self._build_info()
		return observation, reward, self.done, info

	def state(self) -> dict[str, Any]:
		remaining_steps = max(0, self.total_steps - self.current_step_index)
		progress_ratio = self.current_step_index / self.total_steps if self.total_steps else 0.0
		last_action = self.history[-1][0] if self.history else None

		return {
			"current_step_index": self.current_step_index,
			"total_steps": self.total_steps,
			"remaining_steps": remaining_steps,
			"progress_ratio": progress_ratio,
			"done": self.done,
			"last_action": last_action,
			"last_action_reason": self.last_action_reason,
			"incident_state": self._get_incident_state(),
			"correct_steps_count": self.correct_steps_count,
			"wrong_steps_count": self.wrong_steps_count,
			"history": deepcopy(self.history),
		}

	def _build_observation(self, last_action: str | None) -> dict[str, Any]:
		remaining_steps = max(0, self.total_steps - self.current_step_index)
		progress_ratio = self.current_step_index / self.total_steps if self.total_steps else 0.0

		return {
			"description": self.task.description,
			"current_step": self.current_step_index,
			"remaining_steps": remaining_steps,
			"allowed_actions": list(self.task.allowed_actions),
			"action_map": {a: ACTION_MAP[a] for a in self.task.allowed_actions if a in ACTION_MAP},
			"last_action": last_action,
			"last_action_reason": self.last_action_reason,
			"progress_ratio": progress_ratio,
			"incident_state": self._get_incident_state(),
		}

	def _build_info(self) -> dict[str, Any]:
		return {
			"correct_steps_count": self.correct_steps_count,
			"wrong_steps_count": self.wrong_steps_count,
			"history": deepcopy(self.history),
		}
