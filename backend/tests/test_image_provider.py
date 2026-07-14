from __future__ import annotations

import base64
import os

import pytest

from app.image.fake import FakeImageProvider
from app.image.newapi import NewapiImageProvider

_PNG = b"\x89PNG\r\n\x1a\n-fake-bytes"
_PNG_B64 = base64.b64encode(_PNG).decode()


def _resp(content):
    return {"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 42}}


def test_newapi_parses_inline_data_uri(tmp_path):
    def fake_post(url, headers, json):
        assert url.endswith("/v1/chat/completions")
        assert headers["Authorization"].startswith("Bearer ")
        assert json["model"] == "nano-banana-pro-preview"
        return _resp(f"Sure! ![image](data:image/png;base64,{_PNG_B64})")

    p = NewapiImageProvider(
        base_url="http://gw", api_key="k", model="nano-banana-pro-preview",
        output_dir=str(tmp_path), public_base_url="http://host", http_post=fake_post,
    )
    r = p.generate(prompt="gold letter A emblem")
    assert r.mime == "image/png"
    assert r.provider == "newapi"
    assert r.path.endswith(".png") and os.path.exists(r.path)
    assert open(r.path, "rb").read() == _PNG
    assert r.media_url == f"http://host/videos/{os.path.basename(r.path)}"
    assert r.metadata["bytes"] == len(_PNG)


def test_newapi_jpeg_ext_normalized(tmp_path):
    def fake_post(url, headers, json):
        return _resp(f"![i](data:image/jpeg;base64,{_PNG_B64})")

    p = NewapiImageProvider(base_url="http://gw", api_key="k", model="m",
                            output_dir=str(tmp_path), http_post=fake_post)
    r = p.generate(prompt="x")
    assert r.path.endswith(".jpg") and r.mime == "image/jpg"


def test_newapi_refs_use_multimodal_content(tmp_path):
    captured = {}

    def fake_post(url, headers, json):
        captured["body"] = json
        return _resp(f"![i](data:image/png;base64,{_PNG_B64})")

    p = NewapiImageProvider(base_url="http://gw", api_key="k", model="m",
                            output_dir=str(tmp_path), http_post=fake_post)
    p.generate(prompt="same character, new pose", refs=["data:image/png;base64,ABC"])
    content = captured["body"]["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "same character, new pose"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == "data:image/png;base64,ABC"


def test_newapi_no_image_raises(tmp_path):
    def fake_post(url, headers, json):
        return _resp("I can't generate that image, sorry.")

    p = NewapiImageProvider(base_url="http://gw", api_key="k", model="m",
                            output_dir=str(tmp_path), http_post=fake_post)
    with pytest.raises(RuntimeError):
        p.generate(prompt="x")


def test_fake_provider_writes_placeholder(tmp_path):
    p = FakeImageProvider(output_dir=str(tmp_path), public_base_url="http://host")
    r = p.generate(prompt="anything")
    assert r.provider == "fake"
    assert os.path.exists(r.path) and r.path.endswith(".png")
    assert r.metadata["placeholder"] is True


def test_factory_falls_back_to_fake(monkeypatch):
    from app.config import settings
    from app.image.factory import resolve_image_provider

    monkeypatch.setattr(settings, "image_provider", "newapi")
    monkeypatch.setattr(settings, "anthropic_api_key", None)  # incomplete config
    prov = resolve_image_provider()
    assert prov.name == "fake"
