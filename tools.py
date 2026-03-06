import datetime
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

SEARXNG_URL = os.environ.get("TERMINOX_SEARXNG", "http://localhost:8080")


def get_current_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def search(query: str, max_results: int = 5) -> str:
    """Search the web via SearXNG and return top results."""
    params = urllib.parse.urlencode({"q": query, "format": "json"})
    url = f"{SEARXNG_URL}/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        results = data.get("results", [])[:max_results]
        if not results:
            return "No results found."
        lines = []
        for i, res in enumerate(results, 1):
            lines.append(f"{i}. {res.get('title', '(no title)')}")
            lines.append(f"   {res.get('url', '')}")
            snippet = res.get("content", "").strip()
            if snippet:
                lines.append(f"   {snippet}")
        return "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


def scrape(url: str) -> str:
    """Fetch a URL and return its readable text content."""
    from bs4 import BeautifulSoup
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        cap = 10 * 1024
        if len(text.encode()) > cap:
            return text.encode()[:cap].decode("utf-8", errors="ignore") + "\n\n[truncated at 10KB]"
        return text
    except Exception as e:
        return f"Scrape error: {e}"


def fetch_json(url: str) -> str:
    """Fetch a URL and return the response as pretty-printed JSON."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        return json.dumps(data, indent=2)
    except json.JSONDecodeError as e:
        return f"Response is not valid JSON: {e}"
    except Exception as e:
        return f"Fetch error: {e}"


def read_file(path: str) -> str:
    """Read and return the contents of a local file."""
    try:
        cap = 50 * 1024
        with open(path, "rb") as f:
            raw = f.read(cap + 1)
        truncated = len(raw) > cap
        content = raw[:cap].decode("utf-8", errors="replace")
        return content + "\n\n[truncated at 50KB]" if truncated else content
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Read error: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a local file, creating parent directories as needed."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {path}"
    except Exception as e:
        return f"Write error: {e}"


def list_dir(path: str) -> str:
    """List the contents of a directory."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Path not found: {path}"
        if not p.is_dir():
            return f"Not a directory: {path}"
        entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        if not entries:
            return "(empty directory)"
        lines = []
        for e in entries:
            if e.is_dir():
                lines.append(f"[dir]  {e.name}")
            else:
                lines.append(f"[file] {e.name} ({e.stat().st_size} bytes)")
        return "\n".join(lines)
    except Exception as e:
        return f"List error: {e}"


_SHELL_BLOCKLIST = [
    r"rm\s+.*-[a-z]*r",     # rm -r, -rf, -fr, -Rf, etc.
    r"rm\s+.*--recursive",
    r"dd\s+if=",
    r"mkfs",
    r":\(\)\s*\{",   # fork bomb
    r">\s*/dev/",
    r"chmod\s+.*\s+/\s*$",
    r"chown\s+.*\s+/\s*$",
]


def _is_shell_blocked(command: str) -> bool:
    return any(re.search(p, command, re.IGNORECASE) for p in _SHELL_BLOCKLIST)


def run_shell(command: str) -> str:
    """Execute a shell command after blocklist check and user confirmation."""
    if _is_shell_blocked(command):
        return "Blocked: command matches safety blocklist."
    print(f"▸ run_shell: {command} — Allow? [y/N]: ", end="", flush=True)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "Denied by user."
    if answer != "y":
        return "Denied by user."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = (result.stdout + result.stderr).strip()
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Shell error: {e}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Returns the current local date and time.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the web via SearXNG. Returns titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results to return (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scrape",
            "description": "Fetch a URL and return its readable text content (scripts/styles removed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_json",
            "description": "Fetch a URL and return the response body as pretty-printed JSON.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read and return the contents of a local file (up to 50KB).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a local file. Creates parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write to"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the contents of a local directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command. Requires user confirmation. Dangerous commands are blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
        },
    },
]

_REGISTRY: dict[str, Callable[[dict], str]] = {
    "get_current_time": lambda _args: get_current_time(),
    "search": lambda args: search(args["query"], args.get("max_results", 5)),
    "scrape": lambda args: scrape(args["url"]),
    "fetch_json": lambda args: fetch_json(args["url"]),
    "read_file": lambda args: read_file(args["path"]),
    "write_file": lambda args: write_file(args["path"], args["content"]),
    "list_dir": lambda args: list_dir(args["path"]),
    "run_shell": lambda args: run_shell(args["command"]),
}


def execute_tool(name: str, args_json: str) -> str:
    try:
        args = json.loads(args_json) if args_json.strip() else {}
    except json.JSONDecodeError as e:
        return f"Invalid arguments JSON: {e}"
    if not isinstance(args, dict):
        return f"Invalid arguments: expected JSON object, got {type(args).__name__}"
    fn = _REGISTRY.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(args)
    except Exception as e:
        return f"Tool raised an error: {e}"
