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


def test_build_script_prompt_includes_trends_when_given():
    from app.analysis.script import build_script_prompt
    p = build_script_prompt("Topic", _Brief(), trends="Trending now: \"Farm 3 airdrops\" (tiktok)")
    assert "Farm 3 airdrops" in p


def test_build_script_prompt_uses_target_seconds():
    from app.analysis.script import build_script_prompt
    class B:
        main_direction="web3"; sub_niches=["defi"]; tone="punchy"; language="en"
        persona="Nina"; compliance_stance="info_education"; target_seconds=90
    p = build_script_prompt("Topic", B())
    assert "90" in p                      # target seconds surfaced
    # word budget roughly target_seconds * ~2.7
    assert "word" in p.lower()


def test_build_script_prompt_defaults_when_no_target():
    from app.analysis.script import build_script_prompt
    class B:
        main_direction="web3"; sub_niches=[]; tone=None; language="en"; persona=None; compliance_stance="info_education"
    p = build_script_prompt("Topic", B())   # no target_seconds attr -> default 50
    assert "50" in p
