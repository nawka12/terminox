import datetime
from tools import execute_tool, TOOLS, get_current_time


def test_get_current_time_returns_string():
    result = get_current_time()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_current_time_format():
    result = get_current_time()
    datetime.datetime.strptime(result, "%Y-%m-%d %H:%M:%S")


def test_execute_tool_get_current_time():
    result = execute_tool("get_current_time", "{}")
    datetime.datetime.strptime(result, "%Y-%m-%d %H:%M:%S")


def test_execute_tool_unknown():
    result = execute_tool("nonexistent", "{}")
    assert "Unknown tool" in result
    assert "nonexistent" in result


def test_tools_list_structure():
    assert len(TOOLS) >= 1
    for tool in TOOLS:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]


def test_execute_tool_empty_args():
    result = execute_tool("get_current_time", "")
    datetime.datetime.strptime(result, "%Y-%m-%d %H:%M:%S")


def test_execute_tool_whitespace_args():
    result = execute_tool("get_current_time", "   ")
    datetime.datetime.strptime(result, "%Y-%m-%d %H:%M:%S")


def test_execute_tool_malformed_json():
    result = execute_tool("get_current_time", "{bad}")
    assert "Invalid arguments" in result
