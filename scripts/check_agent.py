"""Manual check: repository tools, structured blocks, and edge cases."""

from __future__ import annotations

from app.db import SessionLocal
from app.repositories.agent_repository import AgentRepository
from app.services.agent_blocks import AgentToolEvent, build_agent_blocks
from app.services.agent_service import normalize_agent_reply

db = SessionLocal()
try:
    repo = AgentRepository(db)

    events = [
        AgentToolEvent("get_clinic_overview", repo.get_clinic_overview()),
        AgentToolEvent("get_discharge_stats", repo.get_discharge_stats(days=30)),
        AgentToolEvent("get_patients_by_risk", repo.get_patients_by_risk("critical")),
        AgentToolEvent("get_patient_detail", repo.get_patient_detail("Test Patient")),
        AgentToolEvent("get_patient_detail", repo.get_patient_detail("1")),
        AgentToolEvent("get_patient_detail", repo.get_patient_detail("Missing Person")),
        AgentToolEvent("get_patient_detail", repo.get_patient_detail("+919876543210")),
        AgentToolEvent("get_patient_detail", repo.get_patient_detail("9876543210")),
        AgentToolEvent("get_patient_detail", repo.get_patient_detail("")),
        AgentToolEvent("list_patients", repo.list_patients()),
        AgentToolEvent("get_emergency_patients", repo.get_emergency_patients()),
        AgentToolEvent("get_overdue_followups", repo.get_overdue_followups()),
        AgentToolEvent(
            "search_patients_semantic",
            {"unavailable": True, "reason": "Not available right now", "results": []},
        ),
        AgentToolEvent(
            "search_call_transcripts",
            {"unavailable": True, "reason": "Not available right now", "results": []},
        ),
        AgentToolEvent(
            "get_patients_by_risk",
            {"risk_level": "medium", "count": 0, "patients": []},
        ),
        AgentToolEvent(
            "get_emergency_patients",
            {"count": 0, "emergencies": []},
        ),
        AgentToolEvent(
            "get_overdue_followups",
            {"count": 0, "patients": []},
        ),
        AgentToolEvent(
            "list_patients",
            {"count": 0, "patients": []},
        ),
    ]

    blocks = build_agent_blocks(events)
    print("block order:", [block.type for block in blocks])
    assert [block.type for block in blocks] == sorted(
        [block.type for block in blocks],
        key=lambda t: {
            "kpi_grid": 0,
            "patient_table": 1,
            "emergency_list": 2,
            "patient_search_results": 3,
            "call_search_results": 4,
            "ambiguous_patients": 5,
            "patient_detail": 6,
            "notice": 7,
        }.get(t, 99),
    )

    assert any(block.type == "ambiguous_patients" for block in blocks)
    assert any(block.type == "patient_detail" for block in blocks)
    assert any(
        block.type == "notice" and "not found" in block.title.lower()
        for block in blocks
    )
    assert any(
        block.type == "notice" and "unavailable" in block.title.lower()
        for block in blocks
    )
    assert any(
        block.type == "patient_table" and block.count == 0 for block in blocks
    )
    assert any(
        block.type == "emergency_list" and block.count == 0 for block in blocks
    )
    assert any(
        block.type == "patient_table"
        and block.title == "Overdue follow-ups"
        and block.count == 0
        for block in blocks
    )
    assert any(
        block.type == "patient_table"
        and block.title == "Patients"
        and block.count == 0
        for block in blocks
    )

    cleaned = normalize_agent_reply("There are **2** patients\n\n## Details")
    assert "**" not in cleaned
    assert "##" not in cleaned
    print("cleaned reply:", cleaned)
    print("[ok] steps 16-22 edge cases passed")
finally:
    db.close()
