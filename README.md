# ai-katas

Small daily exercises with the Claude API. Each day has its own folder (`day01`, `day02`, ...).

## Index

| Day | Kata | Notes |
|-----|------|-------|
| 01  | _todo_ |     |

## Setup

1. Install [uv](https://docs.astral.sh/uv/), then run `uv sync`.
2. Put your key in your shell profile, never in the repo:
   `export ANTHROPIC_API_KEY="sk-ant-..."`
3. Run tests: `uv run pytest`
4. Run the linter: `uv run ruff check .`

## Notes on the API

- Models: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5` (no date suffix).
- Do not send `temperature`, `top_p` or `top_k`.
- No assistant prefill. Use structured outputs or instructions.
- Opus 5.5 and Sonnet 5.5 reject forced tool choice.
- Control thinking depth with `effort`.
- Always check `stop_reason` before reading content.

Costs are logged in [costs.md](costs.md).
