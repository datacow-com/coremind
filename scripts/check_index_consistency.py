"""
Lightweight index vs file consistency checker.
- Lists documents in local index and verifies file existence.
- For each chunk's doc_id, check if file exists; reports missing files.
"""

import os

from core.storage.local_index import get_index


def main():
    idx = get_index()
    all_meta = idx.list_all_meta()
    missing = []
    for m in all_meta:
        doc_id = m.get("doc_id")
        path = doc_id
        if not path:
            continue
        if not os.path.exists(path):
            missing.append(path)
    print(f"checked {len(all_meta)} chunks, missing_files={len(missing)}")
    for m in missing[:50]:
        print(f"MISSING: {m}")
    if len(missing) > 50:
        print(f"... ({len(missing)-50} more)")


if __name__ == "__main__":
    main()
