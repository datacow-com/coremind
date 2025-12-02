import asyncio
import io
import zipfile


def build_minimal_pptx(path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        slide1 = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            "<p:cSld>"
            "<p:spTree>"
            "<p:sp>"
            "<p:txBody><a:p><a:r><a:t>Title</a:t></a:r></a:p><a:p><a:r><a:t>Bullet1</a:t></a:r></a:p></p:txBody>"
            "</p:sp>"
            "</p:spTree>"
            "</p:cSld>"
            "</p:sld>"
        )
        z.writestr("ppt/slides/slide1.xml", slide1)
        z.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
    with open(path, "wb") as f:
        f.write(buf.getvalue())


def test_pptx_ingest_to_markdown(tmp_path, monkeypatch):
    from core.ingestion.pptx_ingest import create_pptx_ingest_graph

    pptx_path = tmp_path / "deck.pptx"
    build_minimal_pptx(pptx_path)
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    app = create_pptx_ingest_graph()
    res = asyncio.run(
        app.ainvoke(
            {"file_path": str(pptx_path), "md": None, "meta": {}},
            config={"configurable": {"thread_id": "t"}},
        )
    )
    md = res.get("md") or ""
    assert "# Slide 1" in md
    assert "Title" in md
    assert "- Bullet1" in md
