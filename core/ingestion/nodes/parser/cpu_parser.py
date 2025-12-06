import io
import fitz  # PyMuPDF
import email
from email import policy
from html.parser import HTMLParser
from core.state import IngestState
from core.utils.monitor import ingest_duration

class _HtmlTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip = True
        if tag in {"h1", "h2", "h3"}:
            self.texts.append("\n# ")
        elif tag in {"li"}:
            self.texts.append("\n- ")
        elif tag in {"p"}:
            self.texts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.texts.append(data.strip())

class CpuTextParser:
    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='cpu_parser').time():
            content = state.get('raw_content')
            if not content:
                return state
            
            file_type = state['file_type']
            blocks = []
            
            try:
                if file_type == 'pdf':
                    with fitz.open(stream=content, filetype="pdf") as doc:
                        for page_num, page in enumerate(doc):
                            # Get text blocks
                            text_blocks = page.get_text("blocks")
                            for b in text_blocks:
                                # (x0, y0, x1, y1, "text", block_no, block_type)
                                # block_type: 0 = text, 1 = image
                                if b[6] == 0: # text
                                    blocks.append({
                                        "type": "text",
                                        "content": b[4],
                                        "bbox": [b[0], b[1], b[2], b[3]],
                                        "page": page_num + 1
                                    })
                                # For simplicity, we ignore images in CPU parser or handle differently
                
                elif file_type == 'md':
                    text = content.decode('utf-8', errors='ignore')
                    # Simple split by paragraphs for now
                    paras = text.split('\n\n')
                    for i, p in enumerate(paras):
                        if p.strip():
                            blocks.append({
                                "type": "text",
                                "content": p.strip(),
                                "page": 1,
                                "bbox": None
                            })
                            
                elif file_type == 'html':
                    text = content.decode('utf-8', errors='ignore')
                    parser = _HtmlTextExtractor()
                    parser.feed(text)
                    full_text = "".join(parser.texts)
                    paras = full_text.split('\n\n')
                    for i, p in enumerate(paras):
                        if p.strip():
                            blocks.append({
                                "type": "text",
                                "content": p.strip(),
                                "page": 1,
                                "bbox": None
                            })

                elif file_type == 'eml':
                    msg = email.message_from_bytes(content, policy=policy.default)
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            if ctype == "text/plain":
                                body = part.get_content()
                                break
                    else:
                        body = msg.get_content()
                    
                    blocks.append({
                        "type": "text",
                        "content": f"Subject: {msg.get('subject')}\nFrom: {msg.get('from')}\n\n{body}",
                        "page": 1,
                        "bbox": None
                    })
                
                # TODO: Add python-docx / python-pptx integration here for 'docx'/'pptx'
                
            except Exception as e:
                state['error_log'].append({
                    'stage': 'cpu_parser',
                    'error': str(e),
                    'file_type': file_type
                })
                # Optionally re-raise if we want to fail the whole flow or fallback
                
            state['parsed_blocks'] = blocks
            return state
