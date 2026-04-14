from __future__ import annotations

from typing import Literal, Any
import random
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Difficulty = Literal["easy", "medium", "hard"]

ACTION_MAP = {
	"check_cpu": "Check current CPU and top process list on the affected node",
	"review_logs": "Review recent deployment logs for abnormal worker count or config changes",
	"scale_out_api": "Scale out API replicas by one and verify latency recovers",
	"inspect_db_metrics": "Inspect application metrics for active DB connections versus configured pool size",
	"identify_long_queries": "Identify long-running queries from database monitoring and capture offending endpoints",
	"raise_pool_size": "Temporarily raise connection pool size within safe database limits",
	"throttle_endpoint": "Apply request throttling for the heaviest endpoint and confirm error rate drops",
	"create_optimization_ticket": "Create follow-up ticket for query optimization with captured evidence",
	"declare_incident": "Declare incident severity and freeze non-essential deployments",
	"verify_standby": "Verify standby cluster health and capacity in secondary region",
	"promote_db_replica": "Promote replicated database read-write role in secondary region",
	"update_routing": "Update global traffic routing to direct production traffic to secondary region",
	"run_synthetic_checks": "Run synthetic checks for API, auth, and billing critical paths",
	"publish_status_update": "Confirm error budget stabilization and publish stakeholder status update",
	"open_recovery_workstream": "Open recovery workstream for controlled failback planning",
	"kill_long_query": "Terminate the identified blocking query in the database",
	"restart_worker": "Restart the async worker node experiencing the stall",
	"flush_cache": "Evict the current Redis cache keys causing the memory pressure"
}

ACTION_TO_PATTERN = {
	"check_cpu": "diagnose",
	"review_logs": "investigate",
	"scale_out_api": "mitigate",
	"inspect_db_metrics": "diagnose",
	"identify_long_queries": "investigate",
	"raise_pool_size": "mitigate",
	"kill_long_query": "mitigate",
	"throttle_endpoint": "mitigate",
	"create_optimization_ticket": "follow_up",
	"declare_incident": "escalate",
	"verify_standby": "investigate",
	"promote_db_replica": "mitigate",
	"update_routing": "mitigate",
	"run_synthetic_checks": "verify",
	"publish_status_update": "communicate",
	"open_recovery_workstream": "follow_up",
	"restart_worker": "mitigate",
	"flush_cache": "mitigate"
}

class Task(BaseModel):
	id: str
	name: str
	description: str
	difficulty: Difficulty
	steps: list[str] = Field(min_length=1)
	allowed_actions: list[str] = Field(min_length=1)
	max_steps: int = Field(gt=0)
	parameters: dict[str, Any] = Field(default_factory=dict)

	model_config = ConfigDict(extra="forbid")

	@field_validator("id", "name", "description")
	@classmethod
	def validate_non_empty_text(cls, value: str) -> str:
		cleaned = value.strip()
		if not cleaned:
			raise ValueError("must not be empty")
		return cleaned

	@field_validator("steps", "allowed_actions")
	@classmethod
	def validate_non_empty_items(cls, value: list[str]) -> list[str]:
		cleaned = [item.strip() for item in value]
		if any(not item for item in cleaned):
			raise ValueError("list items must not be empty")
		return cleaned

	@model_validator(mode="after")
	def validate_step_rules(self) -> Task:
		missing_actions = [step for step in self.steps if step not in self.allowed_actions]
		if missing_actions:
			raise ValueError(
				"all steps must be present in allowed_actions; missing: "
				+ ", ".join(missing_actions)
			)
		if self.max_steps < len(self.steps):
			raise ValueError("max_steps must be greater than or equal to the number of steps")
		return self


class TaskGenerator:
	"""Dynamic Factory for generalizing adversarial runbooks."""
    
	@staticmethod
	def generate_cpu_spike() -> Task:
		cpu = random.randint(85, 100)
		svc = random.choice(["API", "DB", "Worker"])
		sev = random.choice(["medium", "high"])
		diff_map: dict[str, Difficulty] = {"medium": "medium", "high": "hard"}
		
		if svc == "API":
			steps = ["check_cpu", "review_logs", "scale_out_api"]
		elif svc == "DB":
			steps = ["check_cpu", "identify_long_queries", "kill_long_query"]
		else: # Worker
			steps = ["check_cpu", "review_logs", "restart_worker"]
		
		# Add decoy actions
		allowed_actions = list(set(steps + ["raise_pool_size", "flush_cache", "update_routing", "run_synthetic_checks"]))
		random.shuffle(allowed_actions)
		
		phrasings = [
			f"Critical alert: {svc} node CPU usage is clamped at {cpu}%.",
			f"Sustained {cpu}% CPU threshold breached on {svc} tier.",
		]
		noise = random.choice([
			" Also observing a slow but steady increase in memory consumption. Memory leak highly suspected.",
			" Multiple widgets show DB connection pools might be near exhaustion, causing downstream CPU thrashing.",
		])
		misleading_signals = random.choice([
			" A responder suggests we arbitrarily 'run_synthetic_checks' or 'flush_cache'.",
			" A senior engineer confidently stated you must 'raise_pool_size' first.",
		])
		
		desc = f"{random.choice(phrasings)}{noise}{misleading_signals} (Severity: {sev})"
		
		return Task.model_validate({
			"id": f"cpu_spike_{str(uuid.uuid4())[:8]}",
			"name": f"Investigate General CPU Spike ({svc})",
			"description": desc,
			"difficulty": diff_map[sev],
			"steps": steps,
			"allowed_actions": allowed_actions,
			"max_steps": len(steps) + 2,
			"parameters": { "cpu_usage": cpu, "service": svc, "severity": sev }
		})

	@staticmethod
	def generate_db_exhaustion() -> Task:
		svc = random.choice(["API", "Worker", "Auth"])
		traffic = random.choice(["peak traffic", "background data sync", "DDoS attempt"])
		
		if svc == "API":
			steps = ["inspect_db_metrics", "throttle_endpoint", "raise_pool_size"]
		elif svc == "Auth":
			steps = ["inspect_db_metrics", "identify_long_queries", "create_optimization_ticket"]
		else:
			steps = ["inspect_db_metrics", "identify_long_queries", "kill_long_query", "restart_worker"]
			
		allowed_actions = list(set(steps + ["scale_out_api", "check_cpu", "flush_cache", "declare_incident"]))
		random.shuffle(allowed_actions)
		
		phrasings = [
			f"The {svc} service is throwing intermittent 500 errors due to exhausted database connections during {traffic}.",
			f"Connection pool limit reached. {svc} failing continuously amidst {traffic}."
		]
		noise = random.choice([
			" CPU metrics on the web tier are flat, but Redis cache evictions are wild.",
			" Some pods in the cluster are entering CrashLoopBackOff due to OOM Kills, not DB errors.",
		])
		misleading_signals = random.choice([
			" The runbook allegedly says to 'scale_out_api' immediately.",
			" You should 'declare_incident' right now to freeze deployments.",
		])
		
		desc = f"{random.choice(phrasings)}{noise}{misleading_signals}"
		
		return Task.model_validate({
			"id": f"db_exhaustion_{str(uuid.uuid4())[:8]}",
			"name": f"Stabilize DB Pool Exhaustion ({svc})",
			"description": desc,
			"difficulty": "medium",
			"steps": steps,
			"allowed_actions": allowed_actions,
			"max_steps": len(steps) + 2,
			"parameters": { "service": svc, "traffic_pattern": traffic }
		})

	@staticmethod
	def generate_k8s_outage() -> Task:
		region = random.choice(["us-east-1", "eu-central-1", "ap-southeast-2"])
		
		steps = [
			"declare_incident", 
			"verify_standby", 
			"promote_db_replica", 
			"update_routing", 
			"publish_status_update"
		]
		allowed_actions = list(set(steps + ["open_recovery_workstream", "throttle_endpoint", "scale_out_api", "run_synthetic_checks"]))
		random.shuffle(allowed_actions)
		
		phrasings = [
			f"A critical control plane outage in {region} prevents scheduling.",
			f"EKS metrics flatlined in {region}. Pods cannot be scheduled."
		]
		noise = random.choice([
			" Secondary metrics suggest read replicas in the same zone are actively serving traffic.",
			" Cloud provider status shows 'investigating' for an unrelated object storage service.",
		])
		misleading_signals = random.choice([
			" First instinct is to 'throttle_endpoint' to buy time.",
			" We can just 'scale_out_api' in the broken region?",
		])
		
		desc = f"{random.choice(phrasings)}{noise}{misleading_signals} Customer traffic must be shifted."
		
		return Task.model_validate({
			"id": f"k8s_outage_{str(uuid.uuid4())[:8]}",
			"name": f"Handle Regional Outage ({region})",
			"description": desc,
			"difficulty": "hard",
			"steps": steps,
			"allowed_actions": allowed_actions,
			"max_steps": len(steps) + 2,
			"parameters": { "region": region }
		})

def list_tasks() -> list[Task]:
	"""Generate a suite of unique dynamic tasks on each invocation."""
	return [
		TaskGenerator.generate_cpu_spike(),
		TaskGenerator.generate_db_exhaustion(),
		TaskGenerator.generate_k8s_outage()
	]

def get_task(task_id: str) -> Task:
	raise NotImplementedError("Dynamic generator implies tasks cannot be directly fetched by ID. Use list_tasks().")
