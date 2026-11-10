"""Keep the operator documentation navigable from the README."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


def test_documentation_links_and_run_guides():
    readme = ROOT / "README.md"
    assert readme.is_file()
    text = readme.read_text("utf-8")
    required = {
        "deployment.md", "CHANGELOG.md", "docs/purpose.md", "docs/guide-web-ui.md",
        "docs/guide-docker-same-device.md", "docs/guide-docker-deployment-device.md",
        "docs/guide-no-docker-same-device.md",
    }
    targets = set(re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text))
    assert required <= targets
    for target in targets:
        if "://" not in target and not target.startswith("/"):
            assert (ROOT / target).is_file(), target
    for guide in required - {"CHANGELOG.md", "docs/purpose.md"}:
        assert "29406" in (ROOT / guide).read_text("utf-8")
