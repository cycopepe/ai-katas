# Day 01 · Kata 1A: streaming chat CLI

A terminal chat with a requirements analyst. You describe a project idea, and the analyst asks one question at a time. When you type `/summary`, it writes the requirements.

The goal was to use the raw Messages API before any framework: no memory on the server side, a system prompt, streaming, and token usage.

A step-by-step explanation of the code is in [code-tour.html](code-tour.html). Download it and open it in a browser.

## Run it

```
uv run --env-file .env python day01/chat.py      # the chat
uv run --env-file .env python day01/compare.py   # one fixed prompt on all three models
uv run pytest day01                              # tests, no network
```

Commands in the chat: `/model [haiku|sonnet|opus]`, `/count <text>`, `/summary`, `/help`, `/quit`.

After each turn the chat prints input tokens, output tokens, the cost of the turn and the session total. When you leave, it adds one line to `costs.md` with the totals of the session.

## Files

- `chat.py`: the chat loop and the streaming call.
- `chat_core.py`: logic without network (prices, commands, error messages, `costs.md` rows). The tests cover this file.
- `system_prompt.md`: the persona. Edit this file to change how the analyst behaves.
- `compare.py`: the price comparison.

## Why the history lives in the code

The Messages API remembers nothing. Every request must contain the whole conversation, so `Session.history` in `chat_core.py` is the only memory the chat has. This has useful effects. You can switch the model in the middle of a chat, because the new model simply receives the same list of messages. You decide what to keep: when a request fails or the model refuses, the code removes that turn, so the history stays valid. And you see the cost clearly: each turn sends all earlier turns again, so the input tokens grow with every message (367, 440, 526 and 587 tokens in a short test).

## Price difference between models

I sent one fixed prompt (a client who describes a gym workout logger and asks for the summary) to the three models, with the same system prompt and the same `effort` (`medium`). Single run, so treat the numbers as an example:

| Model | Tokens in | Tokens out | USD | Compared with Haiku |
|-------|-----------|------------|-----|---------------------|
| Haiku 5.5 | 451 | 1051 | 0.0006 | 1x |
| Sonnet 5.5 | 451 | 747 | 0.0084 | 14.7x |
| Opus 5.5 | 451 | 768 | 0.0172 | 30.1x |

- The input was the same for all three, so the difference comes from the price per token and from the output.
- Haiku wrote the most output tokens and was still 15 to 30 times cheaper. The price per token matters more than the number of tokens here.
- Output tokens include the thinking of the model, which is hidden by default. The visible answers had 305 to 375 words, much less than the output tokens suggest.
- All three answers were complete (`stop_reason` was `end_turn` each time).

## What I learned

- Errors: a bad key gives one readable line, not a stack trace. The SDK has one exception class for each case (key, rate limit, network, server), and the chat turns each into a short message.
- `count_tokens` needs a message to count. The history ends with an assistant message, so `/count` takes the text you plan to send and adds it to the history.
- The system prompt costs tokens on every request: about 330 input tokens before the first word of the client.
- Pricing: the prices in `chat_core.py` come from the Claude API price table cached on 2026-10-06. Check them again if you use this code later.
