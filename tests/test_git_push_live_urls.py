"""Live Cloudflare URL files must publish to GitHub main from any branch."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_git_push_live_urls_script_targets_main():
    script = ROOT / "scripts" / "git_push_live_urls.sh"
    text = script.read_text(encoding="utf-8")
    assert script.is_file()
    assert "push origin" in text
    assert "HEAD:main" in text
    assert "git_auto_push.sh" not in text
    assert "Link.md" in text
    assert ".env" in text  # loaded for GH_TOKEN, never committed


def test_tunnel_notify_uses_live_url_push(tmp_path):
    src = (ROOT / "scripts" / "tunnel_notify.py").read_text(encoding="utf-8")
    assert "git_push_live_urls.sh" in src
    assert 'git_auto_push.sh"' not in src.split("def git_push_link_update")[1][:800]
