import io
import zipfile
import asyncio


def build_minimal_docx(path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        # minimal document.xml with a table and a paragraph
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:tbl>'
            '<w:tr><w:tc><w:p><w:r><w:t>H1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>H2</w:t></w:r></w:p></w:tc></w:tr>'
            '<w:tr><w:tc><w:p><w:r><w:t>V1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>V2</w:t></w:r></w:p></w:tc></w:tr>'
            '</w:tbl>'
            '<w:p><w:r><w:t>Paragraph text.</w:t></w:r></w:p>'
            '</w:body>'
            '</w:document>'
        )
        z.writestr('word/document.xml', xml)
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
    with open(path, 'wb') as f:
        f.write(buf.getvalue())


def test_docx_ingest_to_markdown(tmp_path, monkeypatch):
    from core.ingestion.docx_ingest import create_docx_ingest_graph
    docx_path = tmp_path / 'doc.docx'
    build_minimal_docx(docx_path)
    monkeypatch.setenv('UPLOADS_DIR', str(tmp_path))
    app = create_docx_ingest_graph()
    res = asyncio.run(app.ainvoke({'file_path': str(docx_path), 'md': None, 'meta': {}}, config={'configurable': {'thread_id': 't'}}))
    md = res.get('md') or ''
    assert '| H1 | H2 |' in md
    assert '| V1 | V2 |' in md
    assert 'Paragraph text.' in md
