# Day 01

Two katas, in two folders. [1A streaming chat CLI (`task01_chat/`)](#kata-1a-streaming-chat-cli) and [1B PDF to validated JSON (`task02_pdf/`)](#kata-1b-pdf-to-validated-json).

## Kata 1A: streaming chat CLI

A terminal chat with a requirements analyst. You describe a project idea, and the analyst asks one question at a time. When you type `/summary`, it writes the requirements.

The goal was to use the raw Messages API before any framework: no memory on the server side, a system prompt, streaming, and token usage.

A step-by-step explanation of the code is in [code-tour.html](task01_chat/code-tour.html). Download it and open it in a browser. A real session is in [example-conversation.md](task01_chat/example-conversation.md).

## Run it

```
uv run --env-file .env python day01/task01_chat/chat.py      # the chat
uv run --env-file .env python day01/task01_chat/compare.py   # one fixed prompt on all three models
uv run pytest day01                              # tests, no network
```

Commands in the chat: `/model [haiku|sonnet|opus]`, `/count <text>`, `/summary`, `/help`, `/quit`.

After each turn the chat prints input tokens, output tokens, the cost of the turn and the session total. When you leave, it adds one line to `costs.md` with the totals of the session.

## Files

- `task01_chat/chat.py`: the chat loop and the streaming call.
- `task01_chat/chat_core.py`: logic without network (prices, commands, error messages, `costs.md` rows). The tests cover this file.
- `task01_chat/system_prompt.md`: the persona. Edit this file to change how the analyst behaves.
- `task01_chat/compare.py`: the price comparison.

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

## Kata 1B: PDF to validated JSON

A script that sends a PDF to Claude as a document, and gets back an object that matches a Pydantic model. The JSON is saved next to the PDF.

```
uv run --env-file .env python day01/task02_pdf/pdf_summary.py day01/task02_pdf/pdfs/arxiv-2609.24348.pdf [more.pdf ...] [--model haiku|sonnet|opus]
```

Files:

- `task02_pdf/pdf_summary.py`: the script and the API call (`client.messages.parse` with `output_format=PdfSummary`).
- `task02_pdf/pdf_core.py`: the `PdfSummary` model, the PDF checks, the JSON file name. The tests in `test_pdf_core.py` cover this file.
- `task02_pdf/pdfs/`: the test PDFs and the JSON results. The three `arxiv-*` files are public papers, and the `weird-*` files are the failure tests.

The model has a title, 3 to 5 key points, entities (name and kind), a confidence (`low`, `medium`, `high`) and a list of unclear sections.

### Results (Haiku 5.5, effort medium)

| PDF | Pages | Tokens in | Tokens out | USD | Confidence |
|-----|-------|-----------|------------|-----|------------|
| Agentic AI in the SDLC (2604.26275) | 8 | 25375 | 997 | 0.0030 | high |
| AgentForge (2604.13120) | 10 | 32548 | 1077 | 0.0038 | high |
| AI-SDLC (2609.24348) | 10 | 27404 | 627 | 0.0031 | high |

All three gave valid JSON with no manual cleanup.

### The weird files

| File | What happened |
|------|---------------|
| `weird-fake.pdf` (a text file with a `.pdf` name) | Stopped before the API call: `This file is not a PDF`. No cost. |
| `weird-empty.pdf` (one blank page) | Valid JSON with `confidence: low`, title `Unknown` and the reason in `unclear_sections`. Cost $0.0004. |
| `weird-spanish.pdf` (12 pages of a Spanish paper) | Worked well: `confidence: high`. The summary is in English and it noticed that the file is only an excerpt. It was not a failure. |

The script also turns these cases into one readable line, with no stack trace: a missing file, a file over 32 MB, an API error, a refusal, a reply cut by `max_tokens`, and a reply that breaks the model (for example, 2 key points).

### What I learned

- Tokens: a PDF costs about 2700 to 3400 input tokens per page in these runs, because each page counts as text and as an image. The answer is small (600 to 1100 tokens), so the input is nearly all of the cost.
- The API cannot enforce list sizes. The SDK removes `min_length` and `max_length` from the schema it sends, and checks them after the answer arrives. A wrong size gives a `ValidationError`, which the script reports as a readable message.
- `parsed_output` can be `None`, so check `stop_reason` first, as in 1A.
- A model that does not break does not mean the answer is good. The blank page produced valid JSON, so "valid" and "useful" are different. The `confidence` and `unclear_sections` fields are what tell you.
- Citations and structured outputs cannot be used in the same request (the API returns a 400), so this kata uses structured output only.
- Not done yet: the stretch (Haiku against Sonnet, with a diff).
