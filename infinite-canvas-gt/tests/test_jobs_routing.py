from jobs.models import JobSpec, JobType
from jobs.routing import JobRouter


def _spec(t, provider=None, **kw):
    if t in ("image_to_image", "image_to_video"):
        kw.setdefault("input_image", "/assets/output/x.png")
    return JobSpec(type=t, prompt="x", provider=provider, **kw)


def test_default_routing():
    r = JobRouter()
    assert r.resolve(_spec("text_to_image")).provider == "modelscope"
    assert r.resolve(_spec("image_to_image")).provider == "modelscope"
    assert r.resolve(_spec("text_to_video")).provider == "jimeng"
    assert r.resolve(_spec("image_to_video")).provider == "jimeng"


def test_strategy_selection():
    r = JobRouter()
    assert r.resolve(_spec("text_to_image")).strategy == "image"
    assert r.resolve(_spec("text_to_video")).strategy == "video"
    assert r.resolve(_spec("text_to_image", provider="runninghub")).strategy == "runninghub"
    assert r.resolve(_spec("text_to_image", provider="comfyui")).strategy == "comfyui"
    assert r.resolve(_spec("text_to_video", provider="comfyui")).strategy == "comfyui"


def test_explicit_provider_override():
    r = JobRouter()
    plan = r.resolve(_spec("text_to_image", provider="volcengine"))
    assert plan.provider == "volcengine"
    assert plan.strategy == "image"


def test_fallbacks_for_video():
    r = JobRouter()
    plan = r.resolve(_spec("text_to_video"))  # jimeng primary
    assert "runninghub" in plan.fallbacks
    # 主力就是 runninghub 时，降级链不应再含它自己
    plan2 = r.resolve(_spec("text_to_video", provider="runninghub"))
    assert "runninghub" not in plan2.fallbacks


def test_custom_defaults():
    r = JobRouter(defaults={JobType.TEXT_TO_IMAGE: "openai"})
    assert r.resolve(_spec("text_to_image")).provider == "openai"
