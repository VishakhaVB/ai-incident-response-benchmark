import os
import json
from typing import Any
try:
	from dotenv import load_dotenv
	load_dotenv()
except ImportError:
	pass

import openai

from env import RunbookEnv
from tasks import Task, list_tasks, ACTION_TO_PATTERN
from grader import grade

import sys

# Initialize globally for get_action signature matching
api_key = os.environ.get("API_KEY")
api_base = os.environ.get("API_BASE_URL")

if not api_key or not api_base:
	print("FATAL: API_KEY and API_BASE_URL environment variables must be set.", file=sys.stderr)
	sys.exit(1)

client = openai.Client(api_key=api_key, base_url=api_base)

MEMORY_FILE = "agent_memory.json"

class LongTermMemory:
	"""Persists successful action patterns across benchmark runs to avoid memorization cheating."""
	def __init__(self, file_path: str = MEMORY_FILE):
		self.file_path = file_path
		self.memory = self._load()

	def _load(self) -> dict:
		if os.path.exists(self.file_path):
			try:
				with open(self.file_path, "r") as f:
					return json.load(f)
			except Exception:
				pass
		return {}

	def save(self):
		try:
			with open(self.file_path, "w") as f:
				json.dump(self.memory, f, indent=4)
		except Exception:
			pass

	def add_success(self, incident_type: str, actions: list[str]):
		if incident_type not in self.memory:
			self.memory[incident_type] = []
		
		# Abstraction Mapping (Anti-Cheat)
		pattern = [ACTION_TO_PATTERN.get(act, "unknown") for act in actions]
		
		if pattern not in self.memory[incident_type]:
			self.memory[incident_type].append(pattern)
			self.save()

	def get_strategies(self, incident_type: str) -> str:
		strategies = self.memory.get(incident_type, [])
		if not strategies:
			return "None"
		return "\n".join([f"- Pattern {i+1}: " + " -> ".join(seq) for i, seq in enumerate(strategies)])

long_term_memory = LongTermMemory()


def _planner_agent(observation: dict, allowed_actions: list[str], prev_actions_str: str, lt_strategies: str, previous_failures: str) -> dict:
	system_prompt = (
		"You are an Elite DevOps Planner Agent. Analyze the incident, review previous outcomes, "
		"and generate a strictly structured JSON response representing the step-by-step strategy.\n\n"
		"CRITICAL INSTRUCTIONS:\n"
		"1. Respond ONLY with a valid JSON Object.\n"
		"2. Avoid repeating failed actions from the history.\n"
		"3. Formulate a short, concrete plan matching the allowed actions.\n"
		"4. Your JSON must follow this exact schema:\n"
		"{\n"
		"  \"plan\": [\"actiontoken1\", \"actiontoken2\", \"actiontoken3\"],\n"
		"  \"current_focus\": \"actiontoken1\"\n"
		"}"
	)
	
	user_prompt = (
		f"Incident Description: {observation.get('description', 'Unknown')}\n"
		f"Current Step: {observation.get('current_step', 0)}\n"
		"Previous Actions (This Episode):\n"
		f"{prev_actions_str}\n\n"
		f"Failed Plan Feedbacks:\n"
		f"{previous_failures}\n\n"
		f"Previously Successful Strategy Patterns (Long Term Memory):\n"
		f"{lt_strategies}\n\n"
		f"Allowed Actions: {json.dumps(allowed_actions, indent=2)}\n\n"
		"Output JSON strategy:"
	)
	
	messages = [
		{"role": "system", "content": system_prompt},
		{"role": "user", "content": user_prompt}
	]
	
	try:
		response = client.chat.completions.create(
			model="gpt-4o-mini",
			messages=messages,
			temperature=0.0,
			response_format={"type": "json_object"},
			max_tokens=250,
			timeout=15.0
		)
		raw = response.choices[0].message.content or "{}"
		return json.loads(raw)
	except Exception as e:
		print(f"[Warning] Planner API Error: {e}")
		return {"plan": [], "current_focus": ""}


def _executor_agent(observation: dict, allowed_actions: list[str], prev_actions_str: str, plan_dict: dict) -> str:
	system_prompt = (
		"You are an Intelligent DevOps Executor Action-Gate. Your objective is to validate the Planner's current step and execute it, OR reject it.\n\n"
		"CRITICAL INSTRUCTIONS:\n"
		"1. Analyze the Planner's 'current_focus'.\n"
		"2. If 'current_focus' has already failed in 'Previous Actions', or clearly violates logic, you MUST output the exact word 'REPLAN'.\n"
		"3. If 'current_focus' is logical and safe, MUST output ONLY the validated action token (no explanation).\n"
		"4. Only output tokens from the allowed actions list or 'REPLAN'.\n"
	)
	
	user_prompt = (
		"Planner Context:\n"
		f"{json.dumps(plan_dict, indent=2)}\n\n"
		f"Current Step: {observation.get('current_step', 0)}\n"
		"Previous Actions (This Episode):\n"
		f"{prev_actions_str}\n\n"
		f"Allowed Actions: {json.dumps(allowed_actions, indent=2)}\n\n"
		"What is your final decision? Output token or 'REPLAN':"
	)
	
	messages = [
		{"role": "system", "content": system_prompt},
		{"role": "user", "content": user_prompt}
	]
	
	max_retries = 2
	fallback_action = "REPLAN"

	for attempt in range(max_retries + 1):
		try:
			response = client.chat.completions.create(
				model="gpt-4o-mini",
				messages=messages,
				temperature=0.0,
				max_tokens=20,
				timeout=10.0
			)
			
			raw_output = response.choices[0].message.content or ""
			
			import string
			clean_output = raw_output.lower()
			punct_to_remove = string.punctuation.replace('_', '')
			clean_output = clean_output.strip(punct_to_remove + " \n\r\t")
			
			parsed_token = clean_output.split()[0] if clean_output else ""
			
			if parsed_token == "replan" or parsed_token in allowed_actions:
				if parsed_token == "replan":
					return "REPLAN"
				return parsed_token
			else:
				print(f"[Warning] Parsed token '{parsed_token}' not strictly valid. Retrying...")
				messages.append({"role": "assistant", "content": raw_output})
				messages.append({"role": "user", "content": "Invalid token. Provide ONLY a valid action token or 'REPLAN'."})
				
		except Exception as e:
			print(f"[Warning] Executor API Error: {e}")
	
	return fallback_action


def run_inference(task: Task) -> float:
	print(f"\n--- Starting Elite Multi-Agent Inference for Task: {task.id} ---")
	
	env = RunbookEnv(task)
	obs = env.reset()
	done = False
	
	max_iter = task.max_steps + 8 # Extended to allow replanning cycles
	iter_count = 0
	
	annotated_history = []
	last_step = 0
	
	# Strip UUID noise from dynamic tasks so we reliably map structure
	incident_type = task.id.rsplit('_', 1)[0]
	lt_strategies = long_term_memory.get_strategies(incident_type)
	
	current_plan = {"plan": [], "current_focus": ""}
	previous_failures = ""
	
	while not done and iter_count < max_iter:
		iter_count += 1
		allowed_actions = obs["allowed_actions"]
		action_map = obs["action_map"]
		
		current_step = obs.get("current_step", 0)
		history = env.history
		
		# Decoupled sequence tracking
		if history:
			last_item = history[-1]
			action_name = last_item[0] if isinstance(last_item, tuple) else last_item
			status = "success" if current_step > last_step else "failure"
			if len(annotated_history) < len(history):
				idx = len(annotated_history) + 1
				annotated_history.append(f"{idx}. {action_name} -> {status}")
			
		last_step = current_step
		prev_actions_str = "\n".join(annotated_history) if annotated_history else "None"
		
		# Generate new plan if empty or explicitly commanded
		if not current_plan.get("plan"):
			current_plan = _planner_agent(obs, allowed_actions, prev_actions_str, lt_strategies, previous_failures)
			
		# Execute against current plan
		action = _executor_agent(obs, allowed_actions, prev_actions_str, current_plan)
		
		if action == "REPLAN" or action == "STOP_EXECUTION":
			print("--- Executor triggered REPLAN. Reconstructing strategy. ---")
			previous_failures += f"Failed Focus: {current_plan.get('current_focus', 'None')}\n"
			current_plan = _planner_agent(obs, allowed_actions, prev_actions_str, lt_strategies, previous_failures)
			action = _executor_agent(obs, allowed_actions, prev_actions_str, current_plan)
			if action == "REPLAN" or action == "STOP_EXECUTION":
				# Emergency safe fallback
				action = allowed_actions[0] if allowed_actions else "STOP_EXECUTION"
				if action == "STOP_EXECUTION":
					break
			
		obs, reward, done, info = env.step(action)
		
		# Increment active focus in plan smoothly on success if possible
		if obs.get("current_step", 0) > current_step and current_plan.get("plan"):
			plan_arr = current_plan["plan"]
			current_focus = current_plan.get("current_focus")
			if current_focus in plan_arr:
				f_idx = plan_arr.index(current_focus)
				if f_idx + 1 < len(plan_arr):
					current_plan["current_focus"] = plan_arr[f_idx + 1]
		
		action_desc = action_map.get(action, "Unknown Action")
		progress = obs["progress_ratio"]
		
		step_num = len(info['history'])
		print(f"Step: {step_num} | Action: {action} ({action_desc}) | Reward: {reward:.2f} | Progress: {progress:.2f}")

	final_state = env.state()
	
	action_history = [item[0] if isinstance(item, tuple) else item for item in final_state["history"]]
	grading_result = grade(actions=action_history, correct_steps=task.steps)
	final_score = grading_result["score"]
	
	# Commit successful strategy pattern to Long Term Memory
	if final_score >= 1.0:
		long_term_memory.add_success(incident_type, action_history)
		print(f"[Memory] Recorded successful strategy pattern for '{incident_type}'")
	
	print(f"\n--- Final Score for Task '{task.id}' ---")
	print(f"Score: {final_score:.2f} ({grading_result['accuracy_percentage']:.1f}%)")
	print(f"Correct Matches: {grading_result['correct_matches']} / {grading_result['total_steps']}")
	print(f"Penalties Assessed (Decision Quality): -{grading_result.get('total_penalty', 0.0):.2f}")
	
	return final_score


def main():
	tasks = list_tasks()
	total_score = 0.0
	
	for task in tasks:
		score = run_inference(task)
		total_score += score
		
	avg_score = total_score / len(tasks) if tasks else 0.0
	print("\n" + "="*50)
	print(f"=== OVERALL AVERAGE SCORE: {avg_score:.2f} ===")
	print("="*50 + "\n")


if __name__ == "__main__":
	main()
