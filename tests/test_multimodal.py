from chat import _text_from_content


def test_text_from_plain_string():
    assert _text_from_content("hello world") == "hello world"


def test_text_from_list_extracts_text_parts():
    content = [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        {"type": "text", "text": "describe this image.png"},
    ]
    assert _text_from_content(content) == "describe this image.png"


def test_text_from_list_multiple_text_parts():
    content = [
        {"type": "text", "text": "first"},
        {"type": "text", "text": "second"},
    ]
    assert _text_from_content(content) == "first second"


def test_text_from_empty_list():
    assert _text_from_content([]) == ""


def test_text_from_list_no_text_parts():
    content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]
    assert _text_from_content(content) == ""


def test_text_part_missing_text_key_does_not_raise():
    content = [{"type": "text"}]  # malformed — no "text" key
    assert _text_from_content(content) == ""


def test_text_from_none_returns_empty():
    assert _text_from_content(None) == ""


import base64
from pathlib import Path
from chat import parse_user_input


def test_parse_plain_text_returns_string():
    assert parse_user_input("hello world") == "hello world"


def test_parse_text_with_no_image_extensions_returns_string():
    assert parse_user_input("look at myfile.txt and data.csv") == "look at myfile.txt and data.csv"


def test_parse_detects_image_path(tmp_path):
    img = tmp_path / "photo.png"
    img.write_bytes(b"\x89PNG\r\n")
    result = parse_user_input(f"describe {img}")
    assert isinstance(result, list)
    assert result[-1] == {"type": "text", "text": f"describe {img}"}
    image_part = result[0]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
    b64 = image_part["image_url"]["url"].split(",", 1)[1]
    assert base64.b64decode(b64) == b"\x89PNG\r\n"


def test_parse_skips_nonexistent_path(capsys):
    result = parse_user_input("see /tmp/nonexistent_xyz123.png")
    assert result == "see /tmp/nonexistent_xyz123.png"
    captured = capsys.readouterr()
    assert "not found" in captured.out.lower() or "skipping" in captured.out.lower()


def test_parse_skips_oversized_file(tmp_path, capsys):
    img = tmp_path / "big.jpg"
    img.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
    result = parse_user_input(str(img))
    assert isinstance(result, str)
    captured = capsys.readouterr()
    assert "too large" in captured.out.lower() or "skipping" in captured.out.lower()


def test_parse_multiple_images(tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.jpg"
    a.write_bytes(b"PNG")
    b.write_bytes(b"JPG")
    result = parse_user_input(f"compare {a} and {b}")
    assert isinstance(result, list)
    image_parts = [p for p in result if p["type"] == "image_url"]
    assert len(image_parts) == 2


def test_parse_ignores_http_urls():
    result = parse_user_input("see https://example.com/photo.png")
    assert result == "see https://example.com/photo.png"


def test_parse_jpeg_extension(tmp_path):
    img = tmp_path / "shot.jpeg"
    img.write_bytes(b"JPEG")
    result = parse_user_input(f"look at {img}")
    assert isinstance(result, list)
    assert result[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_parse_all_images_fail_returns_plain_string(capsys):
    result = parse_user_input("/does/not/exist.png")
    assert result == "/does/not/exist.png"
