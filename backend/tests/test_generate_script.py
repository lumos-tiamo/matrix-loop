from app.analysis.script import generate_script, build_script_prompt


class _FakeLLM:
    def __init__(self, resp): self.resp = resp; self.seen = None
    def complete(self, *, system, prompt): self.seen = prompt; return self.resp


class _Brief:
    main_direction = "web3"
    sub_niches = ["空投猎人", "DeFi"]
    tone = "punchy"
    language = "en"
    persona = "Nina"
    compliance_stance = "info_education"


def test_build_script_prompt_includes_brief_and_topic():
    p = build_script_prompt("Airdrop farming 101", _Brief())
    assert "Airdrop farming 101" in p
    assert "web3" in p and "空投猎人" in p and "Nina" in p
    assert "en" in p.lower()
    assert "info" in p.lower() and "not" in p.lower()   # compliance: info/education, not advice


def test_generate_script_returns_llm_text():
    llm = _FakeLLM("Hook: airdrops are free money if you...")
    out = generate_script("Airdrop farming 101", _Brief(), llm)
    assert out.startswith("Hook:")
    assert "Airdrop farming 101" in llm.seen        # topic was in the prompt


def test_build_script_prompt_includes_performance_when_given():
    from app.analysis.script import build_script_prompt
    perf_block = "Past content performance ... Top performers: \"airdrop guide\" (9000 views)"
    p = build_script_prompt("New topic", _Brief(), performance=perf_block)
    assert "airdrop guide" in p
