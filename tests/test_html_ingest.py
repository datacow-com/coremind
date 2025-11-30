import asyncio


def test_html_ingest_to_markdown(tmp_path, monkeypatch):
    from core.ingestion.html_ingest import create_html_ingest_graph
    html = """
    <html>
      <head><title>Test</title><style>.x{}</style></head>
      <body>
        <h1>Main</h1>
        <p>Hello <b>world</b>.</p>
        <ul><li>Item1</li><li>Item2</li></ul>
      </body>
    </html>
    """
    fp = tmp_path / "page.html"
    fp.write_text(html, encoding="utf-8")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    app = create_html_ingest_graph()
    res = asyncio.run(app.ainvoke({"file_path": str(fp), "md": None, "meta": {}}, config={"configurable": {"thread_id": "t"}}))
    md = res.get("md") or ""
    assert "# Main" in md
    assert "Hello" in md
    assert "- Item1" in md
