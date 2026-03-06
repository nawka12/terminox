#!/usr/bin/env python3
"""Simple ollama-like CLI for llama-server."""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown

import session as session_mod
from tools import TOOLS, execute_tool

_console = Console()

HOST  = os.environ.get("TERMINOX_HOST", "127.0.0.1")
PORT  = os.environ.get("TERMINOX_PORT", "8002")
MODEL = os.environ.get("TERMINOX_MODEL", "qwen35-9b-ft")

BASE_URL = f"http://{HOST}:{PORT}"


DIM   = "\033[3;38;5;245m"  # italic medium-light gray
RESET = "\033[0m"

HEADER = "\033[38;5;245m" + r"""
 _                      _
| |_ ___ _ __ _ __ ___ (_)_ __   _____  __
| __/ _ \ '__| '_ ` _ \| | '_ \ / _ \ \/ /
| ||  __/ |  | | | | | | | | | | (_) >  <
 \__\___|_|  |_| |_| |_|_|_| |_|\___/_/\_\
""" + "\033[0m"


def make_prompt_session() -> PromptSession:
    kb = KeyBindings()

    @kb.add("enter")
    def _submit(event):
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")  # Alt+Enter / Meta+Enter
    def _newline(event):
        event.current_buffer.insert_text("\n")

    return PromptSession(key_bindings=kb, multiline=True)


def print_help() -> None:
    print(
        f"{DIM}"
        "Commands:\n"
        "  /system <text>  Set or replace the system prompt\n"
        "  /clear          Clear conversation history (keeps system prompt)\n"
        "  /think          Toggle thinking block visibility\n"
        "  /compact        Manually compact context\n"
        "  /help           Show this message\n"
        "  /exit           Save session and quit\n"
        "  Ctrl+C          Save session and quit\n"
        "  Alt+Enter       Insert newline (or Escape then Enter)"
        f"{RESET}"
    )


def handle_system_command(history: list, text: str) -> None:
    """Set or replace the system prompt in history."""
    msg = {"role": "system", "content": text}
    if history and history[0]["role"] == "system":
        history[0] = msg
    else:
        history.insert(0, msg)


def handle_clear_command(history: list) -> None:
    """Clear history, preserving system prompt if present."""
    if history and history[0]["role"] == "system":
        system = history[0]
        history.clear()
        history.append(system)
    else:
        history.clear()


def _accumulate_tool_call_delta(buf: dict, tc: dict) -> None:
    idx = tc.get("index")
    if idx is None:
        return
    if idx not in buf:
        buf[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
    entry = buf[idx]
    if "id" in tc and not entry["id"]:
        entry["id"] = tc["id"]
    fn = tc.get("function", {})
    if "name" in fn and not entry["function"]["name"]:
        entry["function"]["name"] = fn["name"]
    if "arguments" in fn:
        entry["function"]["arguments"] += fn["arguments"]


def _finalize_tool_calls(buf: dict) -> list:
    return [
        {"id": v["id"], "type": "function", "function": v["function"]}
        for _, v in sorted(buf.items())
    ]


def stream_chat(
    messages: list[dict],
    tools: list | None = None,
    show_thinking: bool = True,
    n_ctx: int | None = None,
) -> tuple[str, list, dict]:
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        **({"tools": tools} if tools else {}),
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    full_response = ""
    in_thinking = False
    t_start: float | None = None
    prompt_tokens = 0
    completion_tokens = 0
    tool_call_buf: dict = {}

    with urllib.request.urlopen(req) as resp:
        for raw_line in resp:
            line = raw_line.decode().strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)

                # usage-only final chunk
                if not chunk.get("choices"):
                    usage = chunk.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                    completion_tokens = usage.get("completion_tokens", completion_tokens)
                    continue

                delta = chunk["choices"][0]["delta"]

                for tc in delta.get("tool_calls", []):
                    _accumulate_tool_call_delta(tool_call_buf, tc)

                thinking = delta.get("reasoning_content", "")
                content  = delta.get("content", "")

                if thinking:
                    if not in_thinking:
                        if t_start is None:
                            t_start = time.monotonic()
                        if show_thinking:
                            print(f"{DIM}<think>", end="", flush=True)
                        else:
                            print(f"{DIM}◆ Thinking...{RESET}", end="", flush=True)
                        in_thinking = True
                    if show_thinking:
                        print(thinking, end="", flush=True)

                if content:
                    if t_start is None:
                        t_start = time.monotonic()
                    if in_thinking:
                        if show_thinking:
                            print(f"</think>{RESET}", flush=True)
                        else:
                            print(f"\r\033[K", end="", flush=True)
                        in_thinking = False
                    full_response += content  # buffer — rendered as markdown after stream

            except (KeyError, json.JSONDecodeError):
                pass

    if in_thinking:
        if show_thinking:
            print(f"</think>{RESET}", flush=True)
        else:
            print(f"\r\033[K", end="", flush=True)

    if full_response:
        _console.print(Markdown(full_response))
    else:
        print()

    if t_start is not None and completion_tokens:
        elapsed = time.monotonic() - t_start
        ctx_info = ""
        if n_ctx:
            fill = (prompt_tokens + completion_tokens) / n_ctx
            ctx_info = f" · ctx {fill:.0%}"
        print(f"{DIM}▸ {completion_tokens} tokens · {completion_tokens / elapsed:.1f} tok/s{ctx_info}{RESET}")

    usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
    return full_response, _finalize_tool_calls(tool_call_buf), usage


def check_health() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=2) as r:
            return b'"ok"' in r.read()
    except Exception:
        return False


def get_context_size() -> int | None:
    """Query the server for its context window size."""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/slots", timeout=2) as r:
            slots = json.loads(r.read())
            if isinstance(slots, list) and slots:
                return slots[0].get("n_ctx")
    except Exception:
        pass
    try:
        with urllib.request.urlopen(f"{BASE_URL}/props", timeout=2) as r:
            props = json.loads(r.read())
            return props.get("default_generation_settings", {}).get("n_ctx")
    except Exception:
        pass
    return None


COMPACT_THRESHOLD = 0.85
MAX_TOOL_ROUNDS = 10


def run_turn(
    history: list[dict],
    show_thinking: bool = True,
    n_ctx: int | None = None,
) -> dict:
    for _round in range(MAX_TOOL_ROUNDS):
        response, tool_calls, usage = stream_chat(history, tools=TOOLS, show_thinking=show_thinking, n_ctx=n_ctx)

        if not tool_calls:
            history.append({"role": "assistant", "content": response})
            return usage

        # Append assistant message that triggered the tool calls
        history.append({
            "role": "assistant",
            "content": response or None,
            "tool_calls": tool_calls,
        })

        # Execute each tool and feed results back
        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            print(f"{DIM}◆ using {name} tool{RESET}", flush=True)
            result = execute_tool(name, args)
            history.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            })
    else:
        history.append({"role": "assistant", "content": "[max tool rounds reached]"})
        return {}


def compact_history(history: list) -> None:
    """Summarize the conversation in-place to free up context space."""
    print(f"\n{DIM}◆ Context almost full — compacting...{RESET}", flush=True)

    system = history[0] if history and history[0]["role"] == "system" else None
    text_messages = [m for m in history if m["role"] in ("user", "assistant") and m.get("content")]
    conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in text_messages)

    summary_request = [{"role": "user", "content": (
        "Summarize the following conversation concisely. Preserve all important context, "
        "decisions, facts, and information needed to continue seamlessly:\n\n" + conversation
    )}]

    summary, _, _ = stream_chat(summary_request, show_thinking=False)

    history.clear()
    if system:
        history.append(system)
    history.append({"role": "user", "content": "[Conversation compacted — summary follows]"})
    history.append({"role": "assistant", "content": summary})
    print(f"{DIM}◆ Done. Conversation replaced with summary.{RESET}\n")


def print_history(history: list) -> None:
    """Replay conversation history to the terminal."""
    for msg in history:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            print(f"{DIM}[system: {content}]{RESET}\n")
        elif role == "user":
            print(f">>> {content}\n")
        elif role == "assistant" and content:
            _console.print(Markdown(content))
            print()


def startup_menu(sessions: list) -> tuple[list, object]:
    """Display session list and return (history, path) for the chosen session.

    Returns ([], None) for new conversation.
    """
    print(f"{DIM}Recent conversations:{RESET}")
    for i, s in enumerate(sessions, 1):
        created = s["created"][:16].replace("T", " ")
        updated = s.get("updated", "")[:16].replace("T", " ")
        ts = f"{created} · updated {updated}" if updated and updated != created else created
        print(f"  {DIM}{i}. [{ts}] {s['preview']}{RESET}")
    print(f"  {DIM}n. Start new conversation{RESET}")

    while True:
        try:
            choice = input("Choose [1-n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return [], None
        if choice in ("n", ""):
            return [], None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                entry = sessions[idx]
                return session_mod.load_session(entry["path"]), entry["path"]
        print("Invalid choice.")


def main():
    parser = argparse.ArgumentParser(description="Chat with a local llama-server.")
    parser.add_argument("--resume", action="store_true", help="Resume a recent conversation.")
    args = parser.parse_args()

    if not check_health():
        print(f"Server not ready at {BASE_URL}. Is llama-server running?")
        sys.exit(1)

    n_ctx = get_context_size()
    print(HEADER)
    print(f"Connected to {MODEL} at {BASE_URL}")
    print('Type "/exit" or Ctrl+C to quit, "/clear" to reset context, "/help" for commands.\n')

    show_thinking = True
    history: list[dict] = []
    session_path = None
    if args.resume:
        sessions = session_mod.list_sessions()
        if sessions:
            history, session_path = startup_menu(sessions)
            if history:
                print_history(history)
        else:
            print(f"{DIM}No saved sessions found.{RESET}\n")

    prompt_session = make_prompt_session()

    def _save_and_quit(msg: str) -> None:
        session_mod.save_session(history, session_path)
        print(msg)

    while True:
        try:
            user_input = prompt_session.prompt(">>> ").strip()
        except KeyboardInterrupt:
            _save_and_quit("\nBye.")
            break
        except EOFError:
            _save_and_quit("\nBye.")
            break

        if not user_input:
            continue
        if user_input == "/exit":
            _save_and_quit("Bye.")
            break
        if user_input == "/help":
            print_help()
            continue
        if user_input == "/system" or user_input.startswith("/system "):
            text = user_input[7:].strip()
            if text:
                handle_system_command(history, text)
                print(f"{DIM}System prompt set.{RESET}")
            else:
                print("Usage: /system <your prompt text>")
            continue
        if user_input == "/clear":
            handle_clear_command(history)
            print("Context cleared.")
            continue
        if user_input == "/think":
            show_thinking = not show_thinking
            state = "visible" if show_thinking else "hidden"
            print(f"{DIM}Thinking {state}.{RESET}")
            continue
        if user_input == "/compact":
            compact_history(history)
            continue

        history.append({"role": "user", "content": user_input})

        try:
            usage = run_turn(history, show_thinking=show_thinking, n_ctx=n_ctx)
            if n_ctx and usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0) >= n_ctx * COMPACT_THRESHOLD:
                compact_history(history)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
