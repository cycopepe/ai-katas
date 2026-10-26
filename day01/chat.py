"""Day 01, kata 1A: a streaming chat CLI on the raw Messages API.

Run: uv run --env-file .env python day01/chat.py
"""

import os
import sys
from pathlib import Path

import anthropic
from chat_core import (
    MODELS,
    PRICES,
    Session,
    append_costs_row,
    cost_usd,
    costs_row,
    describe_error,
    final_text,
    parse_command,
    resolve_model,
    short_name,
)

HERE = Path(__file__).parent
# The persona lives in a text file, so you can change it without touching the code.
SYSTEM_PROMPT = (HERE / "system_prompt.md").read_text().strip()
COSTS_FILE = HERE.parent / "costs.md"
# The longest reply allowed. The hidden thinking of the model also counts inside this limit.
MAX_TOKENS = 8000
EFFORT = "medium"  # the same on every model, so costs are comparable
# What /summary sends. For the API it is a normal user message; the system prompt sets the format.
SUMMARY_REQUEST = "Please write the requirements summary now, in the format from your instructions."

HELP = """Commands:
  /model [haiku|sonnet|opus]  show or change the model
  /count <text>               count the tokens of the next request without sending it
  /summary                    ask the analyst for the final requirements
  /help                       show this help
  /quit                       leave (Ctrl-D works too)"""


def run_turn(client: anthropic.Anthropic, session: Session, user_text: str) -> None:
    """Send one user turn, stream the reply, and keep the history clean when something fails."""
    # The API remembers nothing, so the new message goes into our own history first.
    session.history.append({"role": "user", "content": user_text})
    print(f"\n{short_name(session.model)}> ", end="", flush=True)
    try:
        # The whole history is sent on every request. The system prompt is a separate parameter.
        with client.messages.stream(
            model=session.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=session.history,
            output_config={"effort": EFFORT},
        ) as stream:
            # Print each piece as it arrives. flush=True stops the terminal from waiting.
            for text in stream.text_stream:
                print(text, end="", flush=True)
            # The complete message has the real token counts and the stop reason.
            message = stream.get_final_message()
    # If the request fails, remove the user message. A question without an answer would
    # stay in the history and confuse the next request.
    except KeyboardInterrupt:
        session.history.pop()
        print("\n[interrupted: this turn was dropped]")
        return
    except anthropic.APIError as exc:
        session.history.pop()
        print(f"\n[error] {describe_error(exc)}")
        return

    usd = session.record(session.model, message.usage.input_tokens, message.usage.output_tokens)
    text = final_text(message)
    # Check why the model stopped before trusting the content.
    if message.stop_reason == "refusal":
        session.history.pop()
        print("\n[the model refused this request: this turn was dropped]")
    elif not text:
        session.history.pop()
        print("\n[the model returned no text: this turn was dropped]")
    else:
        # Keep only the text of the reply. Thinking blocks stay out, so a model switch is safe.
        session.history.append({"role": "assistant", "content": text})
        if message.stop_reason == "max_tokens":
            print("\n[warning: the reply was cut because it hit the token limit]")
    print(
        f"\n[{short_name(session.model)} | in {message.usage.input_tokens} | "
        f"out {message.usage.output_tokens} | ${usd:.4f} | session ${session.session_usd():.4f}]"
    )


def run_count(client: anthropic.Anthropic, session: Session, text: str) -> None:
    if not text:
        print("Usage: /count <the message you plan to send>")
        return
    try:
        # The history ends with a reply, so we need the draft text to make a valid request.
        # "history + [...]" builds a new list, so the real history does not change.
        result = client.messages.count_tokens(
            model=session.model,
            system=SYSTEM_PROMPT,
            messages=session.history + [{"role": "user", "content": text}],
        )
    except anthropic.APIError as exc:
        print(f"[error] {describe_error(exc)}")
        return
    input_cost = cost_usd(session.model, result.input_tokens, 0)
    print(
        f"[count] the next request has {result.input_tokens} input tokens "
        f"(about ${input_cost:.4f}, before the reply)"
    )


def run_model(session: Session, arg: str) -> None:
    if not arg:
        print(f"Model: {session.model}. Choices: {', '.join(MODELS)}")
        return
    model = resolve_model(arg)
    if model is None or model not in PRICES:
        print(f"Unknown model '{arg}'. Choices: {', '.join(MODELS)}")
        return
    # Only the model name changes. The new model receives the same history.
    session.model = model
    print(f"Model is now {model}. The history stays the same.")


def save_costs(session: Session) -> None:
    """Write one line with the totals of the whole session, not one line per turn."""
    if not session.totals:
        return
    append_costs_row(COSTS_FILE, costs_row("01", "1A streaming chat CLI", session.totals))
    print(f"Added one line to {COSTS_FILE.name}. Session total: ${session.session_usd():.4f}")


def main() -> int:
    # Stop early, with a clear message, when the key is missing or still the placeholder.
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or "REPLACE_ME" in key:
        print("Set a real ANTHROPIC_API_KEY in .env, then run:")
        print("  uv run --env-file .env python day01/chat.py")
        return 1

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    session = Session()  # the history and the cost totals live here
    print(f"Requirements analyst on {session.model}. Type /help for commands.")
    print("Describe your project idea to start.")
    try:
        while True:
            try:
                line = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            command = parse_command(line)
            if command is None:  # normal chat text
                run_turn(client, session, line)
            elif command.name in ("quit", "exit"):
                break
            elif command.name == "model":
                run_model(session, command.arg)
            elif command.name == "count":
                run_count(client, session, command.arg)
            elif command.name == "summary":
                run_turn(client, session, SUMMARY_REQUEST)
            elif command.name == "help":
                print(HELP)
            else:
                print(f"Unknown command '/{command.name}'. Type /help.")
    finally:
        # Runs on every way out (/quit, Ctrl-D, Ctrl-C), so the costs are always saved.
        save_costs(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
