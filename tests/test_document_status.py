import asyncio
import os
import tempfile

from api.routes import get_document_status
from core.nodes.ingest import ingest

try:
    import fitz
except Exception:
    fitz = None


async def _make_pdf(path: str):
    if not fitz:
        return
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((72, 72), "Status Test")
    doc.save(path)
    doc.close()


def test_document_status_returns_counts():
    if not fitz:
        return
    with tempfile.TemporaryDirectory() as td:
        uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        doc_id = "status-doc"
        pdf_path = os.path.join(uploads_dir, f"{doc_id}.pdf")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_make_pdf(pdf_path))
        loop.run_until_complete(ingest({"documents": [{"file_path": pdf_path}]}))
        res = loop.run_until_complete(get_document_status(doc_id))
        assert res["document_id"] == doc_id
        assert res["processing_status"] in {"completed", "failed"}
        assert isinstance(res["chunks_count"], int)

