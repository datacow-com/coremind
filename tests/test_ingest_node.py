import asyncio
import tempfile
import os

fitz = None
try:
    import fitz  # PyMuPDF
except Exception:
    pass

from core.nodes.ingest import ingest
from core.loaders.visual_pdf_loader import VisualPDFLoader, ParsingRule


async def _create_pdf(tmp_path: str) -> str:
    if not fitz:
        return tmp_path
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test Ingest")
    doc.save(tmp_path)
    doc.close()
    return tmp_path


def test_ingest_with_document():
    with tempfile.TemporaryDirectory() as td:
        pdf_path = os.path.join(td, "ingest.pdf")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_create_pdf(pdf_path))
        state = {"documents": [{"file_path": pdf_path}]}
        result = loop.run_until_complete(ingest(state))
        assert "chunks" in result
        assert isinstance(result["chunks"], list)
        if fitz:
            assert len(result["chunks"]) >= 1

