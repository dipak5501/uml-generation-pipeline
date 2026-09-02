"""Live-demo URL rewrite when Cloudflare tunnels rotate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mod():
    path = ROOT / "scripts" / "tunnel_notify.py"
    spec = importlib.util.spec_from_file_location("tunnel_notify", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_live_demo_markdown_contains_current_urls():
    tn = _mod()
    ui = "https://new-ui-host.trycloudflare.com"
    api = "https://new-api-host.trycloudflare.com"
    block = tn.live_demo_markdown(ui, api, link_md_rel="Link.md", as_of="2026-08-31")
    assert tn.LIVE_DEMO_BEGIN in block and tn.LIVE_DEMO_END in block
    assert f"**Live demo (as of 2026-08-31):**" in block
    assert ui in block and api in block
    assert f"{api}/api/agent" in block
    assert "[Link.md](Link.md)" in block


def test_swap_maps_stale_ui_and_api_hosts():
    tn = _mod()
    text = """
**Live demo (as of 2026-08-27):**
- **UI:** https://orange-fountain-especially-positive.trycloudflare.com
- **API:** https://easter-replication-mug-dee.trycloudflare.com
export UI_URL="https://orange-fountain-especially-positive.trycloudflare.com"
export API_URL="https://easter-replication-mug-dee.trycloudflare.com"
export AGENT_URL="https://easter-replication-mug-dee.trycloudflare.com/api/agent"
"""
    ui = "https://individual-cinema-uri-checkout.trycloudflare.com"
    api = "https://hypothetical-advanced-meanwhile-wow.trycloudflare.com"
    out = tn._swap_public_tunnels(text, ui, api)
    assert "orange-fountain" not in out
    assert "easter-replication" not in out
    assert ui in out
    assert api in out
    assert f"{api}/api/agent" in out


def test_rewrite_live_demo_docs_updates_marked_block(tmp_path, monkeypatch):
    tn = _mod()
    readme = tmp_path / "README.md"
    readme.write_text(
        "intro\n"
        f"{tn.LIVE_DEMO_BEGIN}\n"
        "**Live demo (as of 2026-08-27):**\n\n"
        "- **UI:** https://orange-fountain-especially-positive.trycloudflare.com\n"
        f"{tn.LIVE_DEMO_END}\n"
        "tail\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tn, "LIVE_DEMO_FILES", (readme,))
    monkeypatch.setattr(tn, "LINK_MD_FILE", tmp_path / "Link.md")
    ui = "https://fresh-ui.trycloudflare.com"
    api = "https://fresh-north.trycloudflare.com"
    assert tn.rewrite_live_demo_docs(ui, api, as_of="2026-08-31") is True
    text = readme.read_text(encoding="utf-8")
    assert "orange-fountain" not in text
    assert ui in text and api in text
    assert "as of 2026-08-31" in text
    assert text.startswith("intro\n")
    assert text.endswith("tail\n")
    assert tn.rewrite_live_demo_docs(ui, api, as_of="2026-08-31") is False
