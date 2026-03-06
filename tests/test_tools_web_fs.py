import json
from io import BytesIO
from unittest.mock import patch, MagicMock
import pytest
import tools


# ── helpers ──────────────────────────────────────────────────────────────────

def make_urlopen_response(body: bytes, status: int = 200):
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ── search ────────────────────────────────────────────────────────────────────

SEARXNG_RESPONSE = json.dumps({
    "results": [
        {"title": "Result One", "url": "https://example.com/1", "content": "Snippet one."},
        {"title": "Result Two", "url": "https://example.com/2", "content": "Snippet two."},
        {"title": "Result Three", "url": "https://example.com/3", "content": ""},
    ]
}).encode()


def test_search_returns_formatted_results():
    with patch("urllib.request.urlopen", return_value=make_urlopen_response(SEARXNG_RESPONSE)):
        result = tools.search("python")
    assert "Result One" in result
    assert "https://example.com/1" in result
    assert "Snippet one." in result


def test_search_respects_max_results():
    with patch("urllib.request.urlopen", return_value=make_urlopen_response(SEARXNG_RESPONSE)):
        result = tools.search("python", max_results=1)
    assert "Result One" in result
    assert "Result Two" not in result


def test_search_empty_results():
    body = json.dumps({"results": []}).encode()
    with patch("urllib.request.urlopen", return_value=make_urlopen_response(body)):
        result = tools.search("xyzzy")
    assert "No results" in result


def test_search_network_error():
    with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
        result = tools.search("python")
    assert "error" in result.lower()


# ── scrape ────────────────────────────────────────────────────────────────────

SCRAPE_HTML = b"""
<html><head><title>Test</title></head>
<body>
  <script>alert('x')</script>
  <style>body { color: red }</style>
  <h1>Hello</h1>
  <p>This is the content.</p>
</body></html>
"""


def test_scrape_extracts_text():
    with patch("urllib.request.urlopen", return_value=make_urlopen_response(SCRAPE_HTML)):
        result = tools.scrape("https://example.com")
    assert "Hello" in result
    assert "This is the content." in result


def test_scrape_strips_scripts_and_styles():
    with patch("urllib.request.urlopen", return_value=make_urlopen_response(SCRAPE_HTML)):
        result = tools.scrape("https://example.com")
    assert "alert" not in result
    assert "color: red" not in result


def test_scrape_truncates_at_10kb():
    large_html = b"<p>" + b"x" * 20000 + b"</p>"
    with patch("urllib.request.urlopen", return_value=make_urlopen_response(large_html)):
        result = tools.scrape("https://example.com")
    assert "[truncated" in result
    assert len(result) < 12000


def test_scrape_network_error():
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        result = tools.scrape("https://example.com")
    assert "error" in result.lower()


# ── fetch_json ────────────────────────────────────────────────────────────────

def test_fetch_json_returns_pretty_json():
    body = json.dumps({"key": "value", "num": 42}).encode()
    with patch("urllib.request.urlopen", return_value=make_urlopen_response(body)):
        result = tools.fetch_json("https://api.example.com/data")
    parsed = json.loads(result)
    assert parsed["key"] == "value"
    assert parsed["num"] == 42


def test_fetch_json_invalid_json():
    with patch("urllib.request.urlopen", return_value=make_urlopen_response(b"not json")):
        result = tools.fetch_json("https://api.example.com/data")
    assert "not valid JSON" in result


def test_fetch_json_network_error():
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        result = tools.fetch_json("https://api.example.com/data")
    assert "error" in result.lower()


# ── read_file ─────────────────────────────────────────────────────────────────

def test_read_file_returns_contents(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    result = tools.read_file(str(f))
    assert result == "hello world"


def test_read_file_truncates_at_50kb(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 60000)
    result = tools.read_file(str(f))
    assert "[truncated" in result
    assert len(result) < 55000


def test_read_file_not_found():
    result = tools.read_file("/nonexistent/path/file.txt")
    assert "not found" in result.lower()


# ── write_file ────────────────────────────────────────────────────────────────

def test_write_file_creates_file(tmp_path):
    target = tmp_path / "out.txt"
    result = tools.write_file(str(target), "hello")
    assert target.read_text() == "hello"


def test_write_file_returns_written_path(tmp_path):
    target = tmp_path / "out.txt"
    result = tools.write_file(str(target), "hello")
    assert "Written" in result
    assert "out.txt" in result


def test_write_file_creates_parent_dirs(tmp_path):
    target = tmp_path / "a" / "b" / "out.txt"
    tools.write_file(str(target), "nested")
    assert target.read_text() == "nested"


# ── list_dir ──────────────────────────────────────────────────────────────────

def test_list_dir_shows_files_and_dirs(tmp_path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.txt").write_text("hi")
    result = tools.list_dir(str(tmp_path))
    assert "[dir]" in result
    assert "subdir" in result
    assert "[file]" in result
    assert "file.txt" in result


def test_list_dir_empty(tmp_path):
    result = tools.list_dir(str(tmp_path))
    assert "empty" in result.lower()


def test_list_dir_not_found():
    result = tools.list_dir("/nonexistent/path")
    assert "not found" in result.lower() or "not a directory" in result.lower()


def test_list_dir_on_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    result = tools.list_dir(str(f))
    assert "not a directory" in result.lower()


# ── run_shell ─────────────────────────────────────────────────────────────────

def test_run_shell_blocks_rm_rf():
    result = tools.run_shell("rm -rf /")
    assert "Blocked" in result


def test_run_shell_blocks_dd():
    result = tools.run_shell("dd if=/dev/zero of=/dev/sda")
    assert "Blocked" in result


def test_run_shell_blocks_mkfs():
    result = tools.run_shell("mkfs.ext4 /dev/sda1")
    assert "Blocked" in result


def test_run_shell_blocks_fork_bomb():
    result = tools.run_shell(":(){ :|:& };:")
    assert "Blocked" in result


def test_run_shell_user_denies(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda: "n")
    result = tools.run_shell("echo hello")
    assert "Denied" in result


def test_run_shell_user_approves(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda: "y")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="hello\n", stderr="")
        result = tools.run_shell("echo hello")
    assert "hello" in result


def test_run_shell_captures_stderr(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda: "y")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="error output")
        result = tools.run_shell("bad_command")
    assert "error output" in result


def test_run_shell_no_output(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda: "y")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="")
        result = tools.run_shell("true")
    assert "(no output)" in result
