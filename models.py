from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Action(BaseModel):
	action: str
	timestamp: float | None = None

	model_config = ConfigDict(extra="forbid")

	@field_validator("action")
	@classmethod
	def validate_action(cls, value: str) -> str:
		cleaned = value.strip()
		if not cleaned:
			raise ValueError("action must not be empty")
		return cleaned


class Observation(BaseModel):
	description: str
	current_step: int = Field(ge=0)
	remaining_steps: int = Field(ge=0)
	progress_ratio: float = Field(ge=0.0, le=1.0)
	allowed_actions: list[str] = Field(default_factory=list)
	action_map: dict[str, str] = Field(default_factory=dict)

	model_config = ConfigDict(extra="forbid")

	@field_validator("description")
	@classmethod
	def validate_description(cls, value: str) -> str:
		cleaned = value.strip()
		if not cleaned:
			raise ValueError("description must not be empty")
		return cleaned

	@field_validator("allowed_actions")
	@classmethod
	def validate_allowed_actions(cls, value: list[str]) -> list[str]:
		cleaned = [item.strip() for item in value]
		if any(not item for item in cleaned):
			raise ValueError("allowed_actions must not contain empty items")
		return cleaned


class StepResult(BaseModel):
	observation: Observation
	reward: float
	done: bool
	info: dict[str, Any] = Field(default_factory=dict)

	model_config = ConfigDict(extra="forbid")


class EnvState(BaseModel):
	current_step_index: int = Field(ge=0)
	total_steps: int = Field(ge=0)
	remaining_steps: int = Field(ge=0)
	progress_ratio: float = Field(ge=0.0, le=1.0)
	done: bool
	correct_steps_count: int = Field(ge=0)
	wrong_steps_count: int = Field(ge=0)
	history: list[str] = Field(default_factory=list)

	model_config = ConfigDict(extra="forbid")

	@field_validator("history")
	@classmethod
	def validate_history(cls, value: list[str]) -> list[str]:
		cleaned = [item.strip() for item in value]
		if any(not item for item in cleaned):
			raise ValueError("history must not contain empty items")
		return cleaned
