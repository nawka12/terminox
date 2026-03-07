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
