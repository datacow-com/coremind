import asyncio
import tempfile
import os

fitz = None
try:
    import fitz  # PyMuPDF
except Exception:
    pass

from core.loaders.visual_pdf_loader import VisualPDFLoader, ParsingRule


async def _create_pdf_with_text(tmp_path: str) -> str:
    if not fitz:
        return tmp_path
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "OmniRAG Test Page")
    page.insert_text((72, 130), "This is a sample text for parsing.")
    page.draw_line(p1=(70, 200), p2=(500, 200))
    page.draw_line(p1=(70, 240), p2=(500, 240))
    page.draw_line(p1=(70, 200), p2=(70, 240))
    page.draw_line(p1=(500, 200), p2=(500, 240))
    doc.save(tmp_path)
    doc.close()
    return tmp_path


def test_visual_pdf_loader_runs():
    rule = ParsingRule(prefer_ocr=True)
    loader = VisualPDFLoader(rule)
    with tempfile.TemporaryDirectory() as td:
        pdf_path = os.path.join(td, "sample.pdf")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_create_pdf_with_text(pdf_path))
        chunks = loop.run_until_complete(loader.process_pdf(pdf_path))
        assert isinstance(chunks, list)
        if fitz:
            assert len(chunks) >= 1
            assert all("page_num" in c for c in chunks)

