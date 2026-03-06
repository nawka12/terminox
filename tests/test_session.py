import json
import time
from pathlib import Path
import pytest
import session


MESSAGES = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there"},
]


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path)
    session.save_session(MESSAGES)
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    loaded = session.load_session(files[0])
    assert loaded == MESSAGES


def test_save_skips_empty_history(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path)
    session.save_session([])
    assert list(tmp_path.glob("*.json")) == []


def test_save_skips_no_user_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path)
    session.save_session([{"role": "system", "content": "You are helpful"}])
    assert list(tmp_path.glob("*.json")) == []


def test_list_sessions_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path)
    assert session.list_sessions() == []


def test_list_sessions_returns_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path)
    # Create 7 sessions; expect only 5 returned, most recent first
    paths = []
    for i in range(7):
        msgs = [{"role": "user", "content": f"msg {i}"}]
        session.save_session(msgs)
        time.sleep(0.01)  # ensure distinct mtimes
        paths = list(tmp_path.glob("*.json"))

    results = session.list_sessions()
    assert len(results) == 5
    # Each result is a dict with 'path' and 'preview' keys
    assert all("path" in r and "preview" in r and "created" in r for r in results)


def test_list_sessions_preview_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path)
    long_msg = "x" * 100
    session.save_session([{"role": "user", "content": long_msg}])
    results = session.list_sessions()
    assert len(results[0]["preview"]) <= 63  # 60 chars + "..."
