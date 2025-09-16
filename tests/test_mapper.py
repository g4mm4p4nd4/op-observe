from op_observe.agentic_security import (
    generate_mitigation_checklist,
    map_finding_to_tables,
)
from op_observe.agentic_security.models import RadarFinding


def test_map_prompt_injection_finding():
    finding = RadarFinding(
        id="F-001",
        detector="prompt_injection_scanner",
        tags=("Prompt_Injection",),
    )
    mapping = map_finding_to_tables(finding)
    llm_matches = mapping.categories_for_scheme("OWASP-LLM")
    assert {category.id for category in llm_matches} == {"LLM01"}
    assert mapping.categories_for_scheme("OWASP-Agentic") == ()


def test_map_agentic_tool_abuse_by_detector_only():
    finding = RadarFinding(
        id="F-002",
        detector="tool_abuse_probe",
        tags=(),
    )
    mapping = map_finding_to_tables(finding)
    agentic_matches = mapping.categories_for_scheme("OWASP-Agentic")
    assert {category.id for category in agentic_matches} == {"AA02"}


def test_map_dependency_vulnerability_by_detector():
    finding = RadarFinding(
        id="F-003",
        detector="osv_scanner",
        tags=(),
    )
    mapping = map_finding_to_tables(finding)
    llm_matches = mapping.categories_for_scheme("OWASP-LLM")
    assert {category.id for category in llm_matches} == {"LLM05"}



def test_unmapped_finding_returns_empty_categories():
    finding = RadarFinding(
        id="F-006",
        detector="custom_detector",
        tags=("unexpected",),
    )
    mapping = map_finding_to_tables(finding)
    assert mapping.all_categories() == ()


def test_generate_mitigation_checklist_deduplicates_categories():
    finding_one = RadarFinding(
        id="F-004",
        detector="osv_scanner",
        tags=("dependency_cve",),
    )
    finding_two = RadarFinding(
        id="F-005",
        detector="pip_audit",
        tags=("package_outdated",),
    )

    mapping_one = map_finding_to_tables(finding_one)
    mapping_two = map_finding_to_tables(finding_two)

    checklist = generate_mitigation_checklist([mapping_one, mapping_two])
    assert checklist, "Expected at least one mitigation entry"
    supply_chain_entry = next(
        entry for entry in checklist if entry.category.id == "LLM05"
    )
    assert supply_chain_entry.finding_ids == ("F-004", "F-005")
    assert "Continuously scan dependencies" in supply_chain_entry.mitigations[0]
