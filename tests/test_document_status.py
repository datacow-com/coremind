import asyncio
import importlib.util
import os
import tempfile


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
get_document_status = routes_mod.get_document_status
ingest = ingest_mod.ingest

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
    with tempfile.TemporaryDirectory() as _td:
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
