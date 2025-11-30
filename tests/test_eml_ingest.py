import asyncio


def test_eml_ingest_to_markdown(tmp_path, monkeypatch):
    from email.message import EmailMessage
    from core.ingestion.eml_ingest import create_eml_ingest_graph
    msg = EmailMessage()
    msg["Subject"] = "Hello"
    msg["From"] = "a@example.com"
    msg["To"] = "b@example.com"
    msg.set_content("Body text here")
    fp = tmp_path / "mail.eml"
    with open(fp, "wb") as f:
        f.write(msg.as_bytes())
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    app = create_eml_ingest_graph()
    res = asyncio.run(app.ainvoke({"file_path": str(fp), "md": None, "meta": {}}, config={"configurable": {"thread_id": "t"}}))
    md = res.get("md") or ""
    assert "# Hello" in md
    assert "From: a@example.com" in md
    assert "Body text here" in md
