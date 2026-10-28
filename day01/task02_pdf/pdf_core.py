"""Logic for the day01 PDF summary that needs no network: the schema, PDF checks, file names."""

import base64
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# The API accepts a PDF up to 32 MB in one request.
MAX_PDF_BYTES = 32 * 1024 * 1024


class PdfError(Exception):
    """A problem with the PDF or the answer. The message is written for the user."""


class Entity(BaseModel):
    name: str = Field(description="The name as written in the document")
    kind: Literal["person", "organization", "place", "date", "amount", "other"]


class PdfSummary(BaseModel):
    """What we want from every PDF. The SDK sends this model to the API as a JSON schema."""

    title: str = Field(description="The title of the document. 'Unknown' if there is none")
    # The API cannot enforce list sizes, so the SDK checks min_length and max_length after
    # the answer arrives. A wrong size raises a pydantic ValidationError.
    key_points: list[str] = Field(
        min_length=3, max_length=5, description="The main points, one short sentence each"
    )
    entities: list[Entity] = Field(description="Important people, organizations, places, dates")
    confidence: Literal["low", "medium", "high"] = Field(
        description="How sure you are that the summary is correct and complete"
    )
    unclear_sections: list[str] = Field(
        description="Parts that were hard to read or understand, and why. Empty if none"
    )


def check_pdf(path: Path) -> bytes:
    """Read the file and stop early, with a clear message, when it cannot be a valid PDF."""
    if not path.is_file():
        raise PdfError(f"File not found: {path}")
    data = path.read_bytes()
    if len(data) > MAX_PDF_BYTES:
        raise PdfError(f"The file is {len(data) / 1_048_576:.0f} MB. The limit is 32 MB.")
    # Every PDF starts with "%PDF". This catches a text file that only has a .pdf name.
    if not data.startswith(b"%PDF"):
        raise PdfError("This file is not a PDF (it does not start with %PDF).")
    return data


def document_block(data: bytes) -> dict:
    """The PDF as a message block. Claude reads the pages itself, so we extract no text."""
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(data).decode("utf-8"),
        },
    }


def json_path(pdf: Path) -> Path:
    """The result goes next to the PDF: report.pdf -> report.json."""
    return pdf.with_suffix(".json")


def write_summary(pdf: Path, summary: PdfSummary) -> Path:
    path = json_path(pdf)
    path.write_text(summary.model_dump_json(indent=2) + "\n")
    return path
