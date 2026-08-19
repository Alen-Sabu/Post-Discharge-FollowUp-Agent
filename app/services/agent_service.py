from __future__ import annotations

import logging
import re
from typing import Any

from app.config import settings
from app.models.schemas import AgentChatResponse, AgentMessage
from app.repositories.agent_repository import AgentRepository
from app.services.agent_blocks import (
    AgentToolEvent,
    build_agent_blocks,
)
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


SYSTEM_INSTRUCTION = """
You are AfterCare Assistant, a clinical operations helper for hospital admins.

Tool use is mandatory. For any question about counts, lists, statistics, or a
specific patient, you MUST call the relevant tool first and answer only from its
result. Never say clinic data or tools are unavailable unless a tool you actually
called returned an error or an "unavailable" flag.

Tool selection guide:
- Emergency patients or emergency calls -> get_emergency_patients
- Totals, risk breakdown, overdue follow-ups, pending calls -> get_clinic_overview
- Recent discharges -> get_discharge_stats
- Patients at a specific risk level -> get_patients_by_risk
- One named patient -> get_patient_detail
- Free-text clinical description of patients -> search_patients_semantic
- Symptoms or issues mentioned during calls -> search_call_transcripts

If get_patient_detail returns ambiguous=true with candidates, list those
candidates (id, name, risk, diagnosis) and ask the admin which patient id
to use. Do not guess. When an id is known, call get_patient_detail again
with that numeric id.

Reply style:
- Start with a direct answer to the admin's question.
- Keep the reply to 2-6 short sentences or a few compact bullets.
- State important counts explicitly.
- Return clean plain text. Do not use markdown headings, bold markers, code
  fences, or tables.
- Mention only the most important details; the interface renders full tool
  results as structured cards below your reply.
- Do not produce markdown tables or repeat every row returned by a tool.
- Report zero clearly when a tool returns no records.

Be concise and factual. Do not invent patient data. Never provide medical
diagnosis or treatment advice; summarize recorded clinic data only.
""".strip()


def normalize_agent_reply(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "I could not generate a response from the available clinic data."

    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("```", "").replace("`", "")
    return cleaned.strip()


def _friendly_gemini_error(exc: Exception) -> str:
    """Map provider errors to short user-facing copy. Never forward raw API payloads."""
    message = str(exc)
    lowered = message.lower()

    if (
        "401" in lowered
        or "unauthenticated" in lowered
        or "invalid authentication" in lowered
        or "api key not valid" in lowered
        or "access_token_type_unsupported" in lowered
        or "permission_denied" in lowered
        or "403" in lowered
    ):
        return (
            "The AI service could not authenticate. "
            "Please contact your administrator to check the API configuration."
        )
    if "404" in lowered or "not_found" in lowered or "is not found" in lowered:
        return (
            "The configured AI model is unavailable. "
            "Please contact your administrator."
        )
    if "503" in lowered or "unavailable" in lowered or "high demand" in lowered:
        return (
            "The AI service is temporarily busy. "
            "Please retry in a moment."
        )
    if "429" in lowered or "quota" in lowered or "resource_exhausted" in lowered:
        return (
            "The AI service has reached its current usage limit. "
            "Please try again later."
        )
    if "timeout" in lowered or "timed out" in lowered or "deadline" in lowered:
        return (
            "The AI service took too long to respond. "
            "Please try again."
        )

    # Keep technical detail in logs only (see logger.exception above the raise).
    return (
        "The clinical assistant is temporarily unavailable. "
        "Please try again in a moment."
    )


class AgentServiceError(Exception):
    pass


class AgentService:
    def __init__(self, repo: AgentRepository) -> None:
        self.repo = repo

    def chat(
        self,
        *,
        message: str,
        history: list[AgentMessage] | None = None,
    ) -> AgentChatResponse:
        if not settings.agent_enabled:
            raise AgentServiceError(
                "The clinical assistant is currently disabled."
            )

        if not settings.google_api_key:
            raise AgentServiceError(
                "The clinical assistant is not configured. "
                "Please contact your administrator."
            )

        if not settings.agent_model:
            raise AgentServiceError(
                "The clinical assistant is not configured. "
                "Please contact your administrator."
            )

        tool_events: list[AgentToolEvent] = []
        tools_fns = self._build_tools(tool_events)
        history_contents = self._history_contents(history or [])
        client = genai.Client(api_key=settings.google_api_key)

        try:
            chat = client.chats.create(
                model=settings.agent_model,
                history=history_contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=tools_fns,
                    temperature=0.2,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=8,
                    ),
                ),
            )

            response = chat.send_message(message)
        except Exception as exc:
            logger.exception("Gemini chat failed")
            raise AgentServiceError(_friendly_gemini_error(exc)) from exc

        reply = normalize_agent_reply(getattr(response, "text", None) or "")

        unique_tools: list[str] = []
        seen: set[str] = set()
        for event in tool_events:
            name = event.name
            if name not in seen:
                seen.add(name)
                unique_tools.append(name)

        return AgentChatResponse(
            reply=reply,
            tool_calls_used=unique_tools,
            blocks=build_agent_blocks(tool_events),
        )

    def _build_tools(self, tool_events: list[AgentToolEvent]) -> list[Any]:
        repo = self.repo

        def capture(name: str, result: dict[str, Any]) -> dict[str, Any]:
            tool_events.append(AgentToolEvent(name=name, result=result))
            return result

        def get_clinic_overview() -> dict:
            """Return clinic-wide counts: patients, risk breakdown, emergencies, overdue follow-ups, pending calls."""
            return capture("get_clinic_overview", repo.get_clinic_overview())

        def get_discharge_stats(days: int = 7) -> dict:
            """Return patients discharged in the last N days with diagnosis and risk."""
            return capture("get_discharge_stats", repo.get_discharge_stats(days=days))

        def get_patients_by_risk(level: str) -> dict:
            """Return patients filtered by risk level: low, medium, high, or critical."""
            return capture("get_patients_by_risk", repo.get_patients_by_risk(level))

        def get_patient_detail(name_or_id: str) -> dict:
            """Return one patient's demographics, protocol, and recent call summaries/symptoms by name or id."""
            return capture("get_patient_detail", repo.get_patient_detail(name_or_id))

        def get_emergency_patients() -> dict:
            """Return recent emergency follow-up calls and related patients."""
            return capture("get_emergency_patients", repo.get_emergency_patients())

        def search_patients_semantic(query: str, limit: int = 5) -> dict:
            """Semantic search over patient records for free-text clinical questions."""
            return capture(
                "search_patients_semantic",
                repo.search_patients_semantic(query, limit=limit),
            )

        def search_call_transcripts(query: str, limit: int = 5) -> dict:
            """Semantic search over call summaries/transcripts for symptoms or issues mentioned."""
            return capture(
                "search_call_transcripts",
                repo.search_call_transcripts(query, limit=limit),
            )

        return [
            get_clinic_overview,
            get_discharge_stats,
            get_patients_by_risk,
            get_patient_detail,
            get_emergency_patients,
            search_patients_semantic,
            search_call_transcripts,
        ]

    def _history_contents(
        self,
        history: list[AgentMessage],
    ) -> list[types.Content]:
        contents: list[types.Content] = []
        for item in history[-10:]:
            role = "user" if item.role == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=item.content)],
                )
            )
        return contents
