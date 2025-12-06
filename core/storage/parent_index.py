from typing import Any


class ParentChildIndex:
    def __init__(self) -> None:
        self._children: dict[str, list[dict[str, Any]]] = {}

    def add(self, meta: dict[str, Any]) -> None:
        pid = meta.get("parent_id")
        if not pid:
            return
        arr = self._children.setdefault(str(pid), [])
        arr.append(meta)

    def children(self, parent_id: str) -> list[dict[str, Any]]:
        return list(self._children.get(str(parent_id), []))


_PARENT_INDEX: ParentChildIndex = ParentChildIndex()


def get_parent_index() -> ParentChildIndex:
    return _PARENT_INDEX
