import sys


def run_test(func, name):
    try:
        func()
        print(f"[PASS] {name}")
        return True
    except AssertionError as e:
        print(f"[FAIL] {name}: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {name}: {e}")
        return False


def _load_func(path: str, func: str):
    import importlib.util, os, sys
    sys.path.append(os.path.abspath("."))
    spec = importlib.util.spec_from_file_location("_test_mod", os.path.abspath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return getattr(mod, func)


def main():
    t1 = _load_func("tests/test_rerank_filter.py", "test_rerank_filters_low_scores")
    t2 = _load_func("tests/test_web_search_provider.py", "test_web_search_runs")
    t3 = _load_func("tests/test_hallucination_node.py", "test_hallucination_outputs_score")

    ok = True
    ok &= run_test(t1, "test_rerank_filters_low_scores")
    ok &= run_test(t2, "test_web_search_runs")
    ok &= run_test(t3, "test_hallucination_outputs_score")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
