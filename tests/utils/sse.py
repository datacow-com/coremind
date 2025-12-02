def parse_sse_text(text: str):
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block.startswith("data:"):
            continue
        payload = block[5:].strip()
        events.append(payload)
    return events


def find_event(events, key: str):
    import json

    for e in events:
        try:
            obj = json.loads(e)
            if obj.get("type") == key:
                return obj
        except Exception:
            continue
    return None
