from app.analysis.llm import AnalysisResult, LLMClient


def test_analysis_result_parses_and_defaults():
    r = AnalysisResult(
        positioning_clarity=82.5,
        positioning_label="平价美妆测评",
        content_direction="聚焦百元内产品横评",
    )
    assert r.positioning_clarity == 82.5
    assert r.positioning_label == "平价美妆测评"
    assert r.suggested_topics == []


def test_analysis_result_clamps_clarity():
    assert AnalysisResult(positioning_clarity=150, positioning_label="x", content_direction="y").positioning_clarity == 100.0
    assert AnalysisResult(positioning_clarity=-10, positioning_label="x", content_direction="y").positioning_clarity == 0.0


def test_llm_client_is_protocol_runtime_checkable():
    class Dummy:
        def complete(self, *, system: str, prompt: str) -> str:
            return "{}"
    assert isinstance(Dummy(), LLMClient)
