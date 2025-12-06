import sys


def main(paths: list[str]) -> int:
    for f in paths:
        try:
            with open(f, "rb") as fh:
                src = fh.read()
            compile(src, f, "exec")
        except Exception as e:
            print(f"Syntax error in {f}: {e}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
