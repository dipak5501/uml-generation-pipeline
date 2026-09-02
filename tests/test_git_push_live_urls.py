"""Live Cloudflare URL files must publish to GitHub main from any branch."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_git_push_live_urls_script_targets_main():
    script = ROOT / "scripts" / "git_push_live_urls.sh"
    text = script.read_text(encoding="utf-8")
    assert script.is_file()
    assert "push origin" in text
    assert "git -C" in text
    assert 'cd "$WT"' not in text
    assert "flock" in text
    assert "git_auto_push.sh" not in text
    assert "Link.md" in text
    assert "read_env_key.sh" in text
    assert "source \"$ROOT/.env\"" not in text
    assert "credential.helper=" in text
    assert "401" in text


def test_tunnel_notify_uses_live_url_push():
    src = (ROOT / "scripts" / "tunnel_notify.py").read_text(encoding="utf-8")
    assert "git_push_live_urls.sh" in src
    assert 'git_auto_push.sh"' not in src.split("def git_push_link_update")[1][:800]
    assert "github_url_push.status" in src


def test_read_env_key_strips_cr_and_ignores_junk(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(
        b"MOCK_PROVIDERS=false\n"
        b"GH_TOKEN=github_pat_exampletokenvalue\r\n"
        b"HF_TOKEN=hf_not_this_one\n"
        b"Get Outlook for Mac\n"
    )
    proc = subprocess.run(
        ["bash", str(ROOT / "scripts" / "read_env_key.sh"), "GH_TOKEN", str(env)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout == "github_pat_exampletokenvalue"
    assert "\r" not in proc.stdout
    junk = subprocess.run(
        ["bash", str(ROOT / "scripts" / "read_env_key.sh"), "Get", str(env)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert junk.stdout == ""


def test_read_env_key_last_assignment_wins(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GH_TOKEN=first\nexport GH_TOKEN=second\n", encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(ROOT / "scripts" / "read_env_key.sh"), "GH_TOKEN", str(env)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout == "second"
