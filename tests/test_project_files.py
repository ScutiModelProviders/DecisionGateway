"""Deployment artifacts must describe the gateway service and its fixed port."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_project_deployment_files():
    required = (
        "Dockerfile", "docker-compose.yml", ".env.example", "run.bat", "shell.bat",
        "AGENTS.md", "CLAUDE.md", "CHANGELOG.md", "tools/make_zip.py",
        "tools/publish_live.py", "tools/deploy.local.example.ini",
    )
    assert all((ROOT / name).is_file() for name in required)
    dockerfile = (ROOT / "Dockerfile").read_text("utf-8")
    assert "EXPOSE 29406" in dockerfile and "ffmpeg" not in dockerfile
    compose = (ROOT / "docker-compose.yml").read_text("utf-8")
    assert "name: decisiongateway" in compose and "citadel_core" in compose
    assert "${SERVICE_BIND:-0.0.0.0}:${SERVICE_PORT:-29406}:29406" in compose
    run = (ROOT / "run.bat").read_bytes()
    assert b"REM LABEL: DecisionGateway Service\r\n" in run
    assert b"Piper" not in run and b"Bard" not in run
