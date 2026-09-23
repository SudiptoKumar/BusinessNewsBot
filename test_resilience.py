import ast
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE = (ROOT / "main.py").read_text()
TREE = ast.parse(SOURCE)

assert "EXA_API_KEY = (os.environ.get(\"EXA_API_KEY\") or \"\").strip()" in SOURCE
assert "except ImportError:" in SOURCE and "Exa = None" in SOURCE
assert "exa.get_contents" not in SOURCE, "Exa must not be used for article extraction"
assert "EXA_DISABLED_THIS_RUN = False" in SOURCE
assert "Exa disabled for the remainder of this run" in SOURCE
assert 'bd_candidates = available_candidates("Bangladesh")' in SOURCE
assert 'intl_candidates = available_candidates("International")' in SOURCE
assert 'source_pool="primary"' not in SOURCE[SOURCE.index("def run():"):SOURCE.index("def self_test():")]
assert "Using stored discovery excerpt for article" in SOURCE
assert "_extract_local_article_text" in SOURCE

# Ensure the two Exa call sites have distinct responsibilities: discovery only.
exa_calls = [n for n in ast.walk(TREE) if isinstance(n, ast.Attribute) and n.attr in {"search_and_contents", "get_contents"}]
assert any(n.attr == "search_and_contents" for n in exa_calls)
assert not any(n.attr == "get_contents" for n in exa_calls)

print("RSS-first / Exa-optional resilience tests passed.")
