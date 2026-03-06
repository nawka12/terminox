from chat import _accumulate_tool_call_delta, _finalize_tool_calls


def test_accumulate_single_chunk_with_name():
    buf = {}
    delta_calls = [{"index": 0, "id": "call_abc", "function": {"name": "get_current_time", "arguments": ""}}]
    for tc in delta_calls:
        _accumulate_tool_call_delta(buf, tc)
    assert buf[0]["id"] == "call_abc"
    assert buf[0]["function"]["name"] == "get_current_time"
    assert buf[0]["function"]["arguments"] == ""


def test_accumulate_arguments_across_chunks():
    buf = {}
    chunks = [
        {"index": 0, "id": "call_abc", "function": {"name": "get_current_time", "arguments": ""}},
        {"index": 0, "function": {"arguments": "{}"}},
    ]
    for tc in chunks:
        _accumulate_tool_call_delta(buf, tc)
    assert buf[0]["function"]["arguments"] == "{}"


def test_finalize_tool_calls():
    buf = {
        0: {"id": "call_abc", "function": {"name": "get_current_time", "arguments": "{}"}},
    }
    result = _finalize_tool_calls(buf)
    assert len(result) == 1
    assert result[0]["id"] == "call_abc"
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "get_current_time"


def test_finalize_empty_buf():
    assert _finalize_tool_calls({}) == []


def test_finalize_multiple_tool_calls_ordering():
    buf = {
        1: {"id": "call_2", "function": {"name": "tool_b", "arguments": "{}"}},
        0: {"id": "call_1", "function": {"name": "tool_a", "arguments": "{}"}},
    }
    result = _finalize_tool_calls(buf)
    assert result[0]["id"] == "call_1"
    assert result[1]["id"] == "call_2"


def test_accumulate_chunk_without_function_key():
    buf = {}
    _accumulate_tool_call_delta(buf, {"index": 0, "id": "call_x"})
    assert buf[0]["id"] == "call_x"
    assert buf[0]["function"]["name"] == ""
    assert buf[0]["function"]["arguments"] == ""


def test_accumulate_id_not_overwritten():
    buf = {}
    _accumulate_tool_call_delta(buf, {"index": 0, "id": "call_abc", "function": {"name": "fn", "arguments": ""}})
    _accumulate_tool_call_delta(buf, {"index": 0, "id": "other_id", "function": {"arguments": "{}"}})
    assert buf[0]["id"] == "call_abc"


def test_accumulate_name_not_doubled():
    buf = {}
    _accumulate_tool_call_delta(buf, {"index": 0, "id": "call_abc", "function": {"name": "get_current_time", "arguments": ""}})
    _accumulate_tool_call_delta(buf, {"index": 0, "function": {"name": "get_current_time", "arguments": ""}})
    assert buf[0]["function"]["name"] == "get_current_time"


from unittest.mock import patch


def test_run_turn_no_tool_calls():
    """Model returns a plain response — appends assistant message and returns."""
    from chat import run_turn
    history = [{"role": "user", "content": "Hello"}]
    with patch("chat.stream_chat", return_value=("Hi there!", [], {})):
        run_turn(history)
    assert history[-1] == {"role": "assistant", "content": "Hi there!"}


def test_run_turn_single_tool_call():
    """Model calls one tool — result is fed back, model then responds."""
    from chat import run_turn
    tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "get_current_time", "arguments": "{}"}}]
    responses = [("", tool_calls, {}), ("It is 12:00", [], {})]
    with patch("chat.stream_chat", side_effect=responses), \
         patch("chat.execute_tool", return_value="2026-03-06 12:00:00"):
        history = [{"role": "user", "content": "What time is it?"}]
        run_turn(history)
    # assistant tool-call turn, tool result, final assistant response
    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert history[-1]["content"] == "It is 12:00"


def test_run_turn_max_rounds():
    """Loop terminates after MAX_TOOL_ROUNDS with a fallback message."""
    from chat import run_turn, MAX_TOOL_ROUNDS
    tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "get_current_time", "arguments": "{}"}}]
    with patch("chat.stream_chat", return_value=("", tool_calls, {})), \
         patch("chat.execute_tool", return_value="2026-03-06 12:00:00"):
        history = [{"role": "user", "content": "loop"}]
        run_turn(history)
    assert history[-1]["content"] == "[max tool rounds reached]"
    # MAX_TOOL_ROUNDS assistant + tool messages pairs plus the initial user message
    assert len(history) == 1 + MAX_TOOL_ROUNDS * 2 + 1
