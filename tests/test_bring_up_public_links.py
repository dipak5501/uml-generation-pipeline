"""bring_up_public_links.sh is Mac-only and must fail loudly off Darwin."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_bring_up_public_links_refuses_non_darwin():
    script = ROOT / "scripts" / "bring_up_public_links.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "Darwin" in text
    assert "git_push_live_urls.sh" in text
    if sys.platform == "darwin":
        return
    proc = subprocess.run(
        ["bash", str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 1
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "Mac Studio" in combined


def test_start_public_tunnels_does_not_hide_github_push():
    text = (ROOT / "scripts" / "start_public_tunnels.sh").read_text(encoding="utf-8")
    assert "git_push_live_urls.sh" in text
    assert 'git_push_live_urls.sh" >/dev/null' not in text
    assert "GitHub Link.md was NOT updated" in text
