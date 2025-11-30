import os
import zipfile
import io
import asyncio


def build_minimal_xlsx(path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        # Shared strings: two strings
        ss = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>Header1</t></si><si><t>Header2</t></si>'
            '</sst>'
        )
        z.writestr('xl/sharedStrings.xml', ss)
        # Sheet1 with two rows, first row uses shared strings
        sheet1 = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1">'
            '<c r="A1" t="s"><v>0</v></c>'
            '<c r="B1" t="s"><v>1</v></c>'
            '</row>'
            '<row r="2">'
            '<c r="A2"><v>10</v></c>'
            '<c r="B2"><v>20</v></c>'
            '</row>'
            '</sheetData>'
            '</worksheet>'
        )
        z.writestr('xl/worksheets/sheet1.xml', sheet1)
        # minimal relationships
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
    with open(path, 'wb') as f:
        f.write(buf.getvalue())


def test_xlsx_ingest_to_markdown(tmp_path, monkeypatch):
    from core.ingestion.xlsx_ingest import create_xlsx_ingest_graph
    # prepare xlsx
    xlsx_path = tmp_path / 'book.xlsx'
    build_minimal_xlsx(xlsx_path)
    # ensure uploads dir writable
    monkeypatch.setenv('UPLOADS_DIR', str(tmp_path))
    app = create_xlsx_ingest_graph()
    res = asyncio.run(app.ainvoke({'file_path': str(xlsx_path), 'md': None, 'meta': {}}, config={'configurable': {'thread_id': 't'}}))
    md = res.get('md') or ''
    assert '| Header1 | Header2 |' in md
    assert '| 10 | 20 |' in md
