from datetime import date

from op_observe.agentic_security.loader import (
    get_agentic_ai_mapping,
    get_llm_top10_mapping,
    list_agentic_ai_versions,
    list_llm_top10_versions,
)


def test_llm_top10_mapping_loads_latest_version():
    versions = list_llm_top10_versions()
    assert "2024.1" in versions
    table = get_llm_top10_mapping()
    assert table.version == "2024.1"
    assert table.scheme == "OWASP-LLM"
    assert isinstance(table.published, date)
    prompt_injection = table.category("LLM01")
    assert "Prompt Injection" in prompt_injection.name


def test_agentic_ai_mapping_loads_latest_version():
    versions = list_agentic_ai_versions()
    assert "2024.1" in versions
    table = get_agentic_ai_mapping()
    assert table.version == "2024.1"
    assert table.scheme == "OWASP-Agentic"
    assert isinstance(table.published, date)
    toolchain_abuse = table.category("AA02")
    assert "Toolchain" in toolchain_abuse.name
