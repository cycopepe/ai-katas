"""Logic for the day01 chat CLI that needs no network: prices, commands, errors, costs.md."""

from dataclasses import dataclass, field
from pathlib import Path

import anthropic

# Short names for the /model command, mapped to the exact model IDs (no date suffix).
MODELS = {
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
}

# USD per 1M tokens as (input, output). From the Claude API price table cached on 2026-10-06.
# Haiku 5.5 costs more for prompts over 100K tokens; a chat in this kata never gets there.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Tokens times the price per million tokens. Output tokens include hidden thinking."""
    price_in, price_out = PRICES[model]
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def short_name(model: str) -> str:
    return model.removeprefix("claude-")


def resolve_model(name: str) -> str | None:
    """Accept an alias ("haiku") or a full model ID. Return None when it is not known."""
    name = name.strip().lower()
    if name in MODELS:
        return MODELS[name]
    # A full ID is accepted only if we know its price, so the cost is never a guess.
    return name if name in PRICES else None


@dataclass
class Totals:
    """Tokens and USD used so far with one model."""

    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0


@dataclass
class Session:
    """All the state of a chat. The API remembers nothing, so the history lives here."""

    model: str = MODELS["haiku"]  # the cheapest model is the default
    # Messages in the API format: {"role": "user" | "assistant", "content": "text"}.
    history: list[dict] = field(default_factory=list)
    # One Totals per model, because a chat can use several models.
    totals: dict[str, Totals] = field(default_factory=dict)

    def record(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Add the usage of one turn to the totals. Return the cost of that turn."""
        usd = cost_usd(model, tokens_in, tokens_out)
        total = self.totals.setdefault(model, Totals())  # create the entry on first use
        total.tokens_in += tokens_in
        total.tokens_out += tokens_out
        total.usd += usd
        return usd

    def session_usd(self) -> float:
        return sum(total.usd for total in self.totals.values())


@dataclass
class Command:
    name: str
    arg: str


def parse_command(line: str) -> Command | None:
    """Return a Command for lines that start with "/", and None for normal chat text."""
    if not line.startswith("/"):
        return None
    # "/model opus" -> name "model", arg "opus". The first space splits the two parts.
    name, _, arg = line[1:].partition(" ")
    return Command(name.lower(), arg.strip())


def final_text(message) -> str:
    """The text of a reply. Other block types, such as thinking, are skipped."""
    return "".join(block.text for block in message.content if block.type == "text")


def describe_error(exc: anthropic.APIError) -> str:
    """One readable line for an API failure. Most specific classes come first."""
    if isinstance(exc, anthropic.AuthenticationError):
        return "The API key was rejected. Check ANTHROPIC_API_KEY."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "This API key is not allowed to do that."
    if isinstance(exc, anthropic.NotFoundError):
        return "The model was not found. Check the model name."
    if isinstance(exc, anthropic.RateLimitError):
        wait = exc.response.headers.get("retry-after", "a few")
        return f"Rate limit reached. Try again in {wait} seconds."
    # A timeout is a kind of connection error, so it must be checked first.
    if isinstance(exc, anthropic.APITimeoutError):
        return "The request took too long. Try again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Cannot reach the API. Check your network."
    if isinstance(exc, anthropic.BadRequestError):
        return f"The API refused the request: {exc.message}"
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return f"The API had a problem ({exc.status_code}). Try again later."
        return f"API error {exc.status_code}: {exc.message}"
    return f"API error: {exc}"


def costs_row(day: str, kata: str, totals: dict[str, Totals]) -> str:
    """One markdown table row for costs.md, with the sums over all models used."""
    models = ", ".join(short_name(model) for model in totals)
    tokens_in = sum(total.tokens_in for total in totals.values())
    tokens_out = sum(total.tokens_out for total in totals.values())
    usd = sum(total.usd for total in totals.values())
    return f"| {day} | {kata} | {models} | {tokens_in} | {tokens_out} | {usd:.4f} |"


def append_costs_row(path: Path, row: str) -> None:
    text = path.read_text() if path.exists() else ""
    # A missing final newline would glue the new row to the last line of the table.
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + row + "\n")
