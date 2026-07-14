import pytest

from jobs.models import JobSpec, JobSubmit, JobType


def test_text_to_image_ok():
    spec = JobSpec(type="text_to_image", prompt="a cat")
    assert spec.type == JobType.TEXT_TO_IMAGE
    assert spec.provider is None
    assert spec.params == {}


def test_image_to_image_requires_input_image():
    with pytest.raises(ValueError):
        JobSpec(type="image_to_image", prompt="restyle")


def test_image_to_video_requires_input_image():
    with pytest.raises(ValueError):
        JobSpec(type="image_to_video", prompt="animate")
    ok = JobSpec(type="image_to_video", prompt="animate", input_image="/assets/output/x.png")
    assert ok.input_image == "/assets/output/x.png"


def test_provider_validation_and_normalization():
    assert JobSpec(type="text_to_image", prompt="x", provider="MODELSCOPE").provider == "modelscope"
    with pytest.raises(ValueError):
        JobSpec(type="text_to_image", prompt="x", provider="midjourney")


def test_empty_prompt_rejected():
    with pytest.raises(ValueError):
        JobSpec(type="text_to_image", prompt="")


def test_batch_bounds():
    JobSubmit(jobs=[JobSpec(type="text_to_image", prompt="x")])
    with pytest.raises(ValueError):
        JobSubmit(jobs=[])
    with pytest.raises(ValueError):
        JobSubmit(jobs=[JobSpec(type="text_to_image", prompt="x")] * 101)
