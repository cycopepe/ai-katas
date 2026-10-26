"""Run one fixed prompt on all three models and compare the cost.

Run: uv run --env-file .env python day01/compare.py
"""

import sys

import anthropic
from chat import COSTS_FILE, EFFORT, MAX_TOKENS, SYSTEM_PROMPT
from chat_core import MODELS, Session, append_costs_row, costs_row, describe_error, final_text

PROMPT = (
    "I want a gym workout logger for myself. Only I use it, on an iPhone, and it must work "
    "without internet. I log exercise, sets, reps and weight in kg. I want to see my best "
    "weight for each exercise and a chart of my progress. I do not know yet how to back up "
    "the data. Please write the requirements summary now."
)


def main() -> int:
    client = anthropic.Anthropic()
    session = Session()
    rows = []
    for alias, model in MODELS.items():
        try:
            message = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": PROMPT}],
                output_config={"effort": EFFORT},
            )
        except anthropic.APIError as exc:
            print(f"[error] {alias}: {describe_error(exc)}")
            return 1
        usage = message.usage
        usd = session.record(model, usage.input_tokens, usage.output_tokens)
        words = len(final_text(message).split())
        rows.append(
            (alias, usage.input_tokens, usage.output_tokens, words, usd, message.stop_reason)
        )

    base = rows[0][4]
    print(f"Same prompt, same system prompt, effort={EFFORT}\n")
    print(f"{'model':<8}{'in':>6}{'out':>7}{'words':>7}{'USD':>10}{'vs haiku':>10}  stop")
    for alias, tokens_in, tokens_out, words, usd, stop in rows:
        print(
            f"{alias:<8}{tokens_in:>6}{tokens_out:>7}{words:>7}{usd:>10.4f}"
            f"{usd / base:>9.1f}x  {stop}"
        )

    append_costs_row(COSTS_FILE, costs_row("01", "1A compare models", session.totals))
    print(f"\nAdded one line to {COSTS_FILE.name}. Total: ${session.session_usd():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
