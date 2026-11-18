"""Fails when a shared admin file drifts from a sibling tool service.

Every tool service keeps byte-identical copies of the files in SHARED, except
the lines matched by ALLOWED. The two gateways (ConversationGateway, DecisionGateway)
also keep the admin page and this script in step with each other only (GATEWAY_ONLY):
their page shows the Gateways editor in the sidebar, which the tool services do not.
Run from any repo: python tools/check_sync.py
"""
import difflib
import re
import sys
from pathlib import Path

SIBLINGS = ("Bard", "Scribe", "Converse", "Reader", "Lens", "Mimic", "DecisionGateway", "ConversationGateway")
SHARED = ("src/admin_api.py", "src/tokens.py", "src/middleware.py", "web/playground.js",
          "tests/test_admin_api.py", "tests/test_tokens.py", "tests/seed.py")
GATEWAY_ONLY = ("web/index.html", "tools/check_sync.py")
GATEWAYS = ("DecisionGateway", "ConversationGateway")
ALLOWED = re.compile(r"^(PREFIX = |const CONFIG = )")  # per-project: token prefix and page config


def lines(path: Path) -> list[str]:
    return [("<per-project line>" if ALLOWED.match(line) else line) for line in path.read_text("utf-8").splitlines()]


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    drift = False
    for sibling in SIBLINGS:
        other = here.parent / sibling
        if sibling == here.name or not other.is_dir():
            continue
        for name in SHARED + (GATEWAY_ONLY if sibling in GATEWAYS else ()):
            diff = list(difflib.unified_diff(lines(here / name), lines(other / name), here.name, other.name, lineterm="", n=0))
            if diff:
                drift = True
                print(f"{name} differs from {sibling}:", *diff[:40], sep="\n")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
