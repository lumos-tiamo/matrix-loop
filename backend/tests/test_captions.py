from __future__ import annotations

from app.video.captions import build_ass, chunk_caption


def test_chunk_splits_sentences_and_long_runs():
    chunks = chunk_caption("A. B C D E F G H.", max_words=6)
    assert chunks == ["A", "B C D E F G", "H"]


def test_chunk_empty_returns_empty():
    assert chunk_caption("") == []
    assert chunk_caption("   \n  ") == []


def test_build_ass_has_header_and_one_dialogue_per_chunk():
    ass = build_ass(["hello world", "second line here"], 10.0, resolution=(1080, 1920))
    assert "[Script Info]" in ass
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert ass.count("Dialogue:") == 2


def test_build_ass_allocates_time_by_char_length():
    # two chunks, second is ~2x longer -> gets ~2x the time; first ends near 10*(len1/(len1+len2))
    ass = build_ass(["ab", "abcd"], 6.0)
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogues) == 2
    # first dialogue End timestamp field (index 2 in the comma-split after "Dialogue: ")
    first_end = dialogues[0].split(",")[2]
    assert first_end.startswith("0:00:02")  # 6 * 2/6 = 2.0s


def test_build_ass_empty_chunks_header_only():
    ass = build_ass([], 10.0)
    assert "[Script Info]" in ass
    assert "Dialogue:" not in ass


def test_render_caption_images_writes_opaque_text(tmp_path):
    from app.video.captions import plan_caption_timings, render_caption_images
    timings = plan_caption_timings(["hello world", "second caption line"], 6.0)
    imgs = render_caption_images(timings, resolution=(1080, 1920), out_dir=str(tmp_path))
    assert len(imgs) == 2
    from PIL import Image
    for path, _s, _e in imgs:
        im = Image.open(path)
        assert im.size == (1080, 1920)
        # alpha channel has fully-opaque pixels -> text was actually drawn
        assert im.split()[3].getextrema()[1] == 255
