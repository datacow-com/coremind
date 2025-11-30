import os
from io import BytesIO
from PIL import Image
import asyncio


def make_png_bytes(text="test"):
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def run_image_ingest(tmp_path, monkeypatch):
    from core.ingestion.image_ingest import images_to_md
    # monkeypatch vision_markdown
    from core.llm.gateway import LLMGateway
    async def fake_vision_markdown(self, image_bytes, prompt, model=None):
        return "# Title\n\nA paragraph"
    monkeypatch.setattr(LLMGateway, "vision_markdown", fake_vision_markdown)
    # monkeypatch embedder
    from core.embedding import provider_embedder as pe
    monkeypatch.setattr(pe.Embedder, "embed", lambda self, text: [0.0] * 256)
    # write png
    fp = tmp_path / "img.png"
    with open(fp, "wb") as f:
        f.write(make_png_bytes())
    # ensure uploads dir writable
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    state = {"file_paths": [str(fp)], "md": None, "meta": {}}
    res = await images_to_md(state)
    assert (res.get("md") or "").startswith("# Title")
    return str(fp)


def test_image_ingest_index(tmp_path, monkeypatch):
    fp = asyncio.run(run_image_ingest(tmp_path, monkeypatch))
    # verify metadata listing
    from core.storage.index_router import list_page_meta
    metas = list_page_meta(fp, 1)
    assert isinstance(metas, list)
