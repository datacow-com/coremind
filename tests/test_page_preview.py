import asyncio
import os
import tempfile
import base64
import importlib.util


def _load_module(name: str, rel_path: str):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


routes_mod = _load_module("server_routes_local", "server/routes.py")
ingest_mod = _load_module("ingest_node_local", "core/nodes/ingest.py")
get_page_preview = routes_mod.get_page_preview
ingest = ingest_mod.ingest

try:
    import fitz
except Exception:
    fitz = None


async def _make_pdf_at(path: str) -> None:
    if not fitz:
        return
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Preview Test")
    # draw simple table rectangle
    page.draw_line(p1=(70, 200), p2=(500, 200))
    page.draw_line(p1=(70, 240), p2=(500, 240))
    page.draw_line(p1=(70, 200), p2=(70, 240))
    page.draw_line(p1=(500, 200), p2=(500, 240))
    doc.save(path)
    doc.close()


def test_page_preview_endpoint_like():
    if not fitz:
        return
    with tempfile.TemporaryDirectory() as td:
        uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        doc_id = "test-doc"
        pdf_path = os.path.join(uploads_dir, f"{doc_id}.pdf")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_make_pdf_at(pdf_path))
        loop.run_until_complete(ingest({"documents": [{"file_path": pdf_path}]}))

        res = loop.run_until_complete(get_page_preview(doc_id, 1))
        assert "image_base64" in res
        assert isinstance(res["image_base64"], str)
        # ensure base64 decodable
        base64.b64decode(res["image_base64"])
        assert "bboxes" in res
        assert isinstance(res["bboxes"], list)
