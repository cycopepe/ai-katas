# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`ai-katas` is a public monorepo of small daily exercises with the Claude API. Each kata lives in its own folder (`day01`, `day02`, ...). The root `README.md` is the index and must get a new row for each kata. There is one shared `uv` environment at the root (Python 3.12), not one per kata.

## Commands

- Install: `uv sync`
- All tests: `uv run pytest`
- One test: `uv run pytest day01/task01_chat/test_chat_core.py::test_parse_command`
- Lint: `uv run ruff check .` (add `--fix` to apply fixes)
- Format: `uv run ruff format .`
- Add a dependency: `uv add <pkg>` (use `uv add --dev <pkg>` for dev tools)

Pytest collects from the repo root, so test files in any `dayNN/` folder are found. Kata scripts that call the API run with `uv run --env-file .env python dayNN/<script>.py`. Pytest puts each test file's folder on `sys.path`, so a kata can import its own modules directly, but test file and module names must be unique across days.

## Conventions

- The API key comes from the `ANTHROPIC_API_KEY` environment variable. Never put it in the repo (`.env` is gitignored).
- After every kata, add one row to `costs.md`: day, kata, model, tokens in, tokens out, USD. This log feeds the cost tables in the author's portfolio.

## Claude API rules (as of Oct 2026)

These differ from older API behavior and cause errors if forgotten:

- Model IDs, exactly and without date suffixes: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`.
- Do not send `temperature`, `top_p` or `top_k`. They are rejected.
- Prefilling the assistant turn is not supported. Use structured outputs or instructions.
- Opus 5.5 and Sonnet 5.5 reject forced tool choice (`any` or a named tool). Steer with the prompt, or use structured outputs when only JSON is needed.
- Thinking is adaptive. Control depth with `effort`. Opus 5.5 and Haiku 5.5 default to `medium`.
- Check `stop_reason` before reading content. It can be `max_tokens`, `tool_use` or `refusal`.
