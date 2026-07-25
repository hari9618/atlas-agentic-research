"""Document text-extraction tests — uploads become clean text before indexing."""

from __future__ import annotations

from atlas.core.rag.extract import extract_text

LONG = (
    "Nimbus Robotics reported revenue of 742 million dollars in fiscal 2025, up 34 "
    "percent year over year, with a gross margin of 41 percent and meaningful customer "
    "concentration in its largest pharmacy account."
)


def test_text_file_passes_through():
    text, err = extract_text("profile.txt", LONG.encode("utf-8"))
    assert err is None
    assert "Nimbus" in text


def test_markdown_is_accepted():
    text, err = extract_text("notes.md", ("# Heading\n\n" + LONG).encode("utf-8"))
    assert err is None and "Nimbus" in text


def test_unsupported_type_is_rejected():
    text, err = extract_text("data.csv", b"a,b,c\n1,2,3")
    assert text == "" and err and "Unsupported" in err


def test_non_utf8_text_is_rejected():
    text, err = extract_text("bad.txt", b"\xff\xfe\x00bad bytes")
    assert text == "" and err


def test_too_short_is_rejected():
    text, err = extract_text("tiny.txt", b"hello")
    assert text == "" and err


def test_pdf_text_is_extracted():
    reportlab = __import__("importlib").util.find_spec("reportlab")
    if reportlab is None:
        import pytest

        pytest.skip("reportlab not available to synthesize a test PDF")
    import io

    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, line in enumerate(LONG.split(". ")):
        c.drawString(72, 720 - i * 20, line)
    c.save()
    text, err = extract_text("filing.pdf", buf.getvalue())
    assert err is None
    assert "Nimbus" in text or "revenue" in text.lower()


def test_docx_text_is_extracted():
    import io

    import docx

    d = docx.Document()
    d.add_paragraph(LONG)
    buf = io.BytesIO()
    d.save(buf)
    text, err = extract_text("brief.docx", buf.getvalue())
    assert err is None
    assert "Nimbus" in text
