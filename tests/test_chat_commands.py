from chat import handle_system_command, handle_clear_command


def test_system_sets_new_prompt():
    history = []
    handle_system_command(history, "You are a pirate.")
    assert history == [{"role": "system", "content": "You are a pirate."}]


def test_system_replaces_existing_prompt():
    history = [{"role": "system", "content": "Old prompt"}]
    handle_system_command(history, "New prompt")
    assert history[0]["content"] == "New prompt"
    assert len(history) == 1


def test_system_inserts_before_other_messages():
    history = [{"role": "user", "content": "Hello"}]
    handle_system_command(history, "Be helpful.")
    assert history[0]["role"] == "system"
    assert history[1]["role"] == "user"


def test_clear_removes_non_system_messages():
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    handle_clear_command(history)
    assert history == []


def test_clear_keeps_system_prompt():
    system = {"role": "system", "content": "Be helpful."}
    history = [system, {"role": "user", "content": "Hi"}]
    handle_clear_command(history)
    assert history == [system]


def test_clear_on_empty_history():
    history = []
    handle_clear_command(history)
    assert history == []
