"""Day 01, kata 1B: a PDF in, validated JSON out.

Run: uv run --env-file .env python day01/task02_pdf/pdf_summary.py day01/task02_pdf/pdfs/x.pdf
"""

import argparse
import os
import sys
from pathlib import Path

# chat_core.py (prices, errors, costs.md rows) lives in day01/task01_chat/, so add that folder.
sys.path.insert(0, str(Path(__file__).parent.parent / "task01_chat"))

import anthropic  # noqa: E402
import pydantic  # noqa: E402
from chat_core import (  # noqa: E402
    MODELS,
    Totals,
    append_costs_row,
    cost_usd,
    costs_row,
    describe_error,
    resolve_model,
    short_name,
)
from pdf_core import (  # noqa: E402
    PdfError,
    PdfSummary,
    check_pdf,
    document_block,
    write_summary,
)

COSTS_FILE = Path(__file__).parent.parent.parent / "costs.md"
MAX_TOKENS = 4000
EFFORT = "medium"
SYSTEM_PROMPT = (
    "You summarize documents. Use only what the document says. Do not add facts. "
    "If the document is empty or unreadable, say so in unclear_sections and set the "
    "confidence to low."
)


def summarize(client: anthropic.Anthropic, model: str, pdf: Path) -> tuple[PdfSummary, int, int]:
    """Send one PDF. Return the summary and the tokens used. Raise PdfError with a clear message."""
    data = check_pdf(pdf)  # fails here, with no API call, for a missing or fake file
    try:
        # messages.parse() sends the schema of PdfSummary and builds the object from the reply.
        response = client.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        document_block(data),
                        {"type": "text", "text": "Summarize this document."},
                    ],
                }
            ],
            output_format=PdfSummary,
            output_config={"effort": EFFORT},
        )
    except anthropic.APIError as exc:
        raise PdfError(describe_error(exc)) from exc
    except pydantic.ValidationError as exc:
        # The reply was valid JSON but broke a rule of the model, such as 2 key points.
        problems = "; ".join(error["msg"] for error in exc.errors())
        raise PdfError(f"The answer did not match the schema: {problems}") from exc
    # Check why the model stopped before trusting the content.
    if response.stop_reason == "refusal":
        raise PdfError("The model refused to summarize this document.")
    if response.stop_reason == "max_tokens":
        raise PdfError("The answer was cut because it hit the token limit.")
    if response.parsed_output is None:
        raise PdfError("The model returned no summary.")
    usage = response.usage
    return response.parsed_output, usage.input_tokens, usage.output_tokens


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize PDFs into validated JSON.")
    parser.add_argument("pdfs", nargs="+", type=Path, help="one or more PDF files")
    parser.add_argument("--model", default="haiku", help="haiku, sonnet or opus (default: haiku)")
    args = parser.parse_args()

    model = resolve_model(args.model)
    if model is None:
        print(f"Unknown model '{args.model}'. Choices: {', '.join(MODELS)}")
        return 1
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or "REPLACE_ME" in key:
        print("Set a real ANTHROPIC_API_KEY in .env, then run with --env-file .env")
        return 1

    client = anthropic.Anthropic()
    total = Totals()
    failed = 0
    for pdf in args.pdfs:
        try:
            summary, tokens_in, tokens_out = summarize(client, model, pdf)
        except PdfError as exc:
            failed += 1
            print(f"[failed] {pdf.name}: {exc}")
            continue
        usd = cost_usd(model, tokens_in, tokens_out)
        total.tokens_in += tokens_in
        total.tokens_out += tokens_out
        total.usd += usd
        out = write_summary(pdf, summary)
        print(
            f"[ok] {pdf.name} -> {out.name} | {short_name(model)} | in {tokens_in} | "
            f"out {tokens_out} | ${usd:.4f} | confidence {summary.confidence}"
        )

    if total.tokens_in:  # write one line for the whole run, only if tokens were used
        row = costs_row("01", "1B PDF to JSON", {model: total})
        append_costs_row(COSTS_FILE, row)
        print(f"Added one line to {COSTS_FILE.name}. Run total: ${total.usd:.4f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
