import anthropic
import httpx2
import pytest
from chat_core import (
    MODELS,
    Session,
    append_costs_row,
    cost_usd,
    costs_row,
    describe_error,
    final_text,
    parse_command,
    resolve_model,
)


def make_status_error(cls, status, headers=None):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, headers=headers, request=request)
    return cls("boom", response=response, body=None)


def test_cost_usd_uses_the_price_of_each_model():
    assert cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert cost_usd("claude-sonnet-5-5", 1_000_000, 0) == pytest.approx(2.00)
    assert cost_usd("claude-opus-5-5", 0, 1_000_000) == pytest.approx(20.00)


def test_resolve_model_accepts_aliases_and_full_ids():
    assert resolve_model("Haiku") == MODELS["haiku"]
    assert resolve_model("claude-opus-5-5") == "claude-opus-5-5"
    assert resolve_model("gpt-4") is None


def test_parse_command():
    assert parse_command("hello there") is None
    command = parse_command("/model Sonnet")
    assert (command.name, command.arg) == ("model", "Sonnet")
    command = parse_command("/count   some text here ")
    assert (command.name, command.arg) == ("count", "some text here")
    assert parse_command("/quit").arg == ""


def test_session_totals_add_up_per_model():
    session = Session()
    session.record("claude-haiku-5-5", 1000, 500)
    session.record("claude-haiku-5-5", 1000, 500)
    session.record("claude-opus-5-5", 1000, 500)
    assert session.totals["claude-haiku-5-5"].tokens_in == 2000
    assert session.totals["claude-haiku-5-5"].tokens_out == 1000
    expected = cost_usd("claude-haiku-5-5", 2000, 1000) + cost_usd("claude-opus-5-5", 1000, 500)
    assert session.session_usd() == pytest.approx(expected)


def test_history_survives_a_model_switch():
    session = Session()
    session.history.append({"role": "user", "content": "hi"})
    session.model = MODELS["opus"]
    assert session.history == [{"role": "user", "content": "hi"}]


def test_final_text_ignores_blocks_that_are_not_text():
    class Block:
        def __init__(self, type, text=""):
            self.type = type
            self.text = text

    class Message:
        content = [Block("thinking"), Block("text", "Hello "), Block("text", "world")]

    assert final_text(Message()) == "Hello world"


def test_describe_error_gives_one_readable_line():
    auth = make_status_error(anthropic.AuthenticationError, 401)
    assert "API key" in describe_error(auth)

    limited = make_status_error(anthropic.RateLimitError, 429, {"retry-after": "30"})
    assert "30 seconds" in describe_error(limited)

    server = make_status_error(anthropic.InternalServerError, 500)
    assert "500" in describe_error(server)

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    assert "network" in describe_error(anthropic.APIConnectionError(request=request))
    assert "too long" in describe_error(anthropic.APITimeoutError(request=request))


def test_costs_row_lists_every_model_used():
    session = Session()
    session.record("claude-haiku-5-5", 100, 50)
    session.record("claude-opus-5-5", 200, 100)
    row = costs_row("01", "1A streaming chat CLI", session.totals)
    assert row.startswith("| 01 | 1A streaming chat CLI | haiku-5-5, opus-5-5 | 300 | 150 | ")
    assert row.endswith(" |")


def test_append_costs_row_keeps_the_table_together(tmp_path):
    path = tmp_path / "costs.md"
    path.write_text("| Day |\n|-----|")  # no final newline
    append_costs_row(path, "| 01 |")
    assert path.read_text() == "| Day |\n|-----|\n| 01 |\n"
