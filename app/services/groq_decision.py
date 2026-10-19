"""Groq implementation of the provider-neutral decision contract."""
from __future__ import annotations

import json
import os

from app.services.decision import DecisionAction, DecisionEngine, WorkContext, WorkDecision


class GroqDecisionEngine:
    """Makes an advisory decision; it never starts, cancels, or saves work itself."""

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-20b") -> None:
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_environment(cls) -> "GroqDecisionEngine | None":
        api_key = os.environ.get("GROQ_API_KEY")
        return cls(api_key, os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")) if api_key else None

    def decide(self, context: WorkContext) -> WorkDecision:
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError("The groq package is not installed.") from exc

        schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": [item.value for item in DecisionAction]},
                "intent": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "task_name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "planned_minutes": {"anyOf": [{"type": "integer", "minimum": 1, "maximum": 240}, {"type": "null"}]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reason_code": {"type": "string"},
            },
            "required": ["action", "intent", "task_name", "planned_minutes", "confidence", "reason_code"],
            "additionalProperties": False,
        }
        response = Groq(api_key=self.api_key).chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": (
                    "You are a personal work-flow router. Return only a decision for the supplied "
                    "state. You are advisory: never claim work has been completed. If there is an "
                    "active session, choose resume_session. If there is insufficient information to "
                    "suggest a concrete task, choose ask_for_work."
                )},
                {"role": "user", "content": json.dumps(context.as_prompt_state(), ensure_ascii=False)},
            ],
            response_format={"type": "json_schema", "json_schema": {"name": "work_decision", "strict": True, "schema": schema}},
            temperature=0,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Groq returned no decision content.")
        return self._parse(json.loads(content))

    @staticmethod
    def _parse(data: dict) -> WorkDecision:
        return WorkDecision(
            action=DecisionAction(data["action"]),
            intent=data["intent"],
            task_name=data["task_name"],
            planned_minutes=data["planned_minutes"],
            confidence=float(data["confidence"]),
            reason_code=data["reason_code"],
        )


class ResilientDecisionEngine:
    """Uses Groq when configured, otherwise (or on failure) uses the offline policy."""

    def __init__(self, primary: DecisionEngine | None, fallback: DecisionEngine) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_provider = "rule_based"

    def decide(self, context: WorkContext) -> WorkDecision:
        if self.primary is not None:
            try:
                decision = self.primary.decide(context)
                self.last_provider = "groq"
                return decision
            except Exception:
                pass
        self.last_provider = "rule_based"
        return self.fallback.decide(context)
