import base64

import pdf_core
import pytest
from pdf_core import PdfError, PdfSummary, check_pdf, document_block, json_path, write_summary
from pydantic import ValidationError


def make_summary(**changes) -> dict:
    data = {
        "title": "A paper",
        "key_points": ["one", "two", "three"],
        "entities": [{"name": "Ada", "kind": "person"}],
        "confidence": "high",
        "unclear_sections": [],
    }
    return data | changes


def test_check_pdf_accepts_a_pdf(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 rest")
    assert check_pdf(pdf) == b"%PDF-1.4 rest"


def test_check_pdf_rejects_missing_fake_and_large_files(tmp_path, monkeypatch):
    with pytest.raises(PdfError, match="not found"):
        check_pdf(tmp_path / "missing.pdf")

    fake = tmp_path / "fake.pdf"
    fake.write_text("plain text")
    with pytest.raises(PdfError, match="not a PDF"):
        check_pdf(fake)

    monkeypatch.setattr(pdf_core, "MAX_PDF_BYTES", 5)
    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-1.4 rest")
    with pytest.raises(PdfError, match="limit"):
        check_pdf(big)


def test_document_block_is_base64_pdf():
    block = document_block(b"%PDF-1.4")
    assert block["type"] == "document"
    assert block["source"]["media_type"] == "application/pdf"
    assert base64.standard_b64decode(block["source"]["data"]) == b"%PDF-1.4"


def test_summary_accepts_valid_data_and_rejects_bad_data():
    assert PdfSummary.model_validate(make_summary()).title == "A paper"
    with pytest.raises(ValidationError):  # only 2 key points
        PdfSummary.model_validate(make_summary(key_points=["one", "two"]))
    with pytest.raises(ValidationError):  # 6 key points
        PdfSummary.model_validate(make_summary(key_points=list("abcdef")))
    with pytest.raises(ValidationError):  # not one of low, medium, high
        PdfSummary.model_validate(make_summary(confidence="sure"))


def test_write_summary_saves_json_next_to_the_pdf(tmp_path):
    pdf = tmp_path / "report.pdf"
    assert json_path(pdf) == tmp_path / "report.json"
    out = write_summary(pdf, PdfSummary.model_validate(make_summary()))
    assert out == tmp_path / "report.json"
    # The file can be read back into the same model.
    assert PdfSummary.model_validate_json(out.read_text()).key_points == ["one", "two", "three"]
