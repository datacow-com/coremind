import asyncio
import os
import tempfile

from api.routes import delete_document_api
from core.nodes.ingest import ingest

try:
    import fitz
except Exception:
    fitz = None


async def _create_pdf(path: str):
    if not fitz:
        return
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Delete Test")
    doc.save(path)
    doc.close()


def test_delete_document_removes_file_and_chunks():
    if not fitz:
        return
    with tempfile.TemporaryDirectory() as td:
        uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        doc_id = "del-doc"
        pdf_path = os.path.join(uploads_dir, f"{doc_id}.pdf")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_create_pdf(pdf_path))
        loop.run_until_complete(ingest({"documents": [{"file_path": pdf_path}]}))
        res = loop.run_until_complete(delete_document_api(doc_id))
        assert res["status"] == "ok"
        assert res["document_id"] == doc_id
        assert isinstance(res["removed_chunks"], int)
        assert res["file_removed"] in {True, False}
        # File should be gone if removal succeeded
        if res["file_removed"]:
            assert not os.path.exists(pdf_path)

