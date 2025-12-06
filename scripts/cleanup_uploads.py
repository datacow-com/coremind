import os
import time
from pathlib import Path


def cleanup_dir(base: str, max_age_hours: int = 72, dry_run: bool = False) -> list[str]:
    removed: list[str] = []
    now = time.time()
    cutoff = now - max_age_hours * 3600
    p = Path(base)
    if not p.exists():
        return removed
    for f in p.glob("*"):
        try:
            if f.is_dir():
                continue
            st = f.stat()
            if st.st_mtime < cutoff:
                if not dry_run:
                    f.unlink(missing_ok=True)
                removed.append(str(f))
        except Exception:
            continue
    return removed


def main():
    base = os.environ.get("UPLOADS_DIR") or os.path.join(os.getcwd(), "data", "uploads", "tmp")
    max_age = int(os.environ.get("CLEANUP_MAX_AGE_HOURS", "72"))
    dry_run = os.environ.get("CLEANUP_DRY_RUN", "0") == "1"
    removed = cleanup_dir(base, max_age_hours=max_age, dry_run=dry_run)
    print(f"cleanup complete, removed={len(removed)}")
    if dry_run:
        for f in removed:
            print(f"[dry-run] would remove: {f}")


if __name__ == "__main__":
    main()
