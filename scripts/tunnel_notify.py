#!/usr/bin/env python3
"""Publish tunnel URLs to .env and notify via SMTP."""
from __future__ import annotations

import argparse
import json
import re
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data/run/last_notified_tunnels.json"
UI_URL_FILE = ROOT / "data/run/public_ui_url.txt"
API_URL_FILE = ROOT / "data/run/public_api_url.txt"
LINK_FILE = ROOT / "Link"
LINK_MD_FILE = ROOT / "Link.md"
DEFAULT_NOTIFY_EMAIL = "dipak.yadav5501@gmail.com"


def _clean_url(url: str) -> str:
    """Normalize a public URL; reject multi-line / control-character garbage."""
    cleaned = (url or "").strip().splitlines()[0].strip()
    if any(ord(ch) < 32 for ch in cleaned):
        raise ValueError(f"URL contains control characters: {cleaned!r}")
    if not cleaned.startswith("https://") or "trycloudflare.com" not in cleaned:
        raise ValueError(f"Unexpected public tunnel URL: {cleaned!r}")
    if "api.trycloudflare.com" in cleaned:
        raise ValueError(f"Bogus api.trycloudflare.com URL: {cleaned!r}")
    return cleaned.rstrip("/")


def write_link_files(ui_url: str, api_url: str) -> None:
    """Keep repo-root Link + Link.md current (no secrets)."""
    from datetime import datetime, timezone

    ui = _clean_url(ui_url)
    api = _clean_url(api_url)
    env = load_env()
    adapter = (env.get("FINETUNED_ADAPTER_PATH") or "").strip()
    if not adapter:
        for candidate in (
            "models/uml-plantuml-lora-200k",
            "models/uml-plantuml-lora-100k",
            "models/uml-plantuml-lora",
        ):
            if (ROOT / candidate).exists():
                adapter = candidate
                break
        else:
            adapter = "models/uml-plantuml-lora"
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    LINK_FILE.write_text(
        "\n".join(
            [
                "Open this URL from any device / any network (Mac Studio server):",
                "",
                ui,
                "",
                f"UI:  {ui}",
                f"API: {api}",
                "",
                "Local (this Mac only):",
                "  UI  http://127.0.0.1:8501",
                "  API http://127.0.0.1:8000",
                f"Adapter: {adapter}",
                "",
                f"Updated: {updated}",
                "URLs change when Cloudflare quick tunnels restart.",
                "Canonical files: data/run/public_ui_url.txt  data/run/public_api_url.txt",
                "",
            ]
        ),
        encoding="utf-8",
    )

    LINK_MD_FILE.write_text(
        "\n".join(
            [
                "# Remote access — UML-Pipeline (Mac Studio server)",
                "",
                "This **Mac Studio** runs the always-on UML-Pipeline server. Keep the **Dipak Yadav** "
                "macOS account logged in (screen lock is fine; use Fast User Switch for other users — "
                "**do not Log Out**).",
                "",
                "## Open from any device",
                "",
                f"**Live UI:** [{ui}]({ui})",
                "",
                "| Endpoint | URL |",
                "|----------|-----|",
                f"| Public UI (browser, any network) | {ui} |",
                f"| Public API (docs / exports) | {api} |",
                "| Local Streamlit (this Mac) | http://127.0.0.1:8501 |",
                "| Local FastAPI (this Mac) | http://127.0.0.1:8000 |",
                "",
                "Quick-tunnel URLs **change every time tunnels restart**. Auto-updated by "
                "`scripts/tunnel_notify.py` whenever tunnels publish. Canonical copies: "
                "`data/run/public_ui_url.txt` and `data/run/public_api_url.txt`.",
                "",
                f"Updated: {updated}",
                "",
                "## Authentication",
                "",
                "`API_ACCESS_TOKEN` must be set in **`.env` on this Mac** (never commit). "
                "Streamlit sends `Authorization: Bearer …` automatically.",
                "",
                "## Troubleshooting",
                "",
                "| Symptom | Fix |",
                "|---------|-----|",
                "| Cloudflare **429 / 1015** | Wait 15–30 min, then `bash scripts/start_public_tunnels.sh` |",
                "| Local UI/API down | `bash scripts/macos_server_status.sh` or reinstall LaunchAgents |",
                "| Stale Link | `bash scripts/ensure_public_tunnel.sh` (or wait for tunnel-monitor) |",
                "",
                "See also: [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md)",
                "",
            ]
        ),
        encoding="utf-8",
    )


def load_env(path: Path | None = None) -> dict[str, str]:
    env: dict[str, str] = {}
    p = path or ROOT / ".env"
    if not p.is_file():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


def smtp_config(env: dict[str, str] | None = None) -> dict[str, str]:
    e = env or load_env()
    return {
        "host": e.get("SMTP_HOST", "smtp.gmail.com"),
        "port": e.get("SMTP_PORT", "587"),
        "user": e.get("SMTP_USER", ""),
        "password": e.get("SMTP_PASSWORD", ""),
        "notify": e.get("NOTIFY_EMAIL", DEFAULT_NOTIFY_EMAIL) or DEFAULT_NOTIFY_EMAIL,
    }


def configured(env: dict[str, str] | None = None) -> bool:
    c = smtp_config(env)
    return bool(c["user"] and c["password"] and c["notify"])


def update_env_urls(ui_url: str, api_url: str) -> None:
    ui_url = _clean_url(ui_url)
    api_url = _clean_url(api_url)
    p = ROOT / ".env"
    if p.is_file():
        text = p.read_text(encoding="utf-8")
        updates = {
            "API_BASE_URL": "http://127.0.0.1:8000",
            "PUBLIC_UI_URL": ui_url,
            "PUBLIC_API_URL": api_url,
        }
        for key, value in updates.items():
            pattern = rf"^{re.escape(key)}=.*$"
            replacement = f"{key}={value}"
            if re.search(pattern, text, flags=re.M):
                text = re.sub(pattern, replacement, text, flags=re.M)
            else:
                text = text.rstrip() + f"\n{replacement}\n"
        # Remove orphan bare trycloudflare lines (breaks `source .env`).
        text = re.sub(
            r"(?m)^https://[a-zA-Z0-9.-]+\.trycloudflare\.com\s*$",
            "",
            text,
        )
        text = re.sub(r"\n{3,}", "\n\n", text)
        p.write_text(text, encoding="utf-8")
    UI_URL_FILE.parent.mkdir(parents=True, exist_ok=True)
    UI_URL_FILE.write_text(ui_url + "\n", encoding="utf-8")
    API_URL_FILE.write_text(api_url + "\n", encoding="utf-8")
    write_link_files(ui_url, api_url)


def fetch_ok(url: str, timeout: float = 15.0) -> bool:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "uml-pipeline-tunnel-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def check_tunnels(ui_url: str | None = None, api_url: str | None = None) -> tuple[bool, str]:
    try:
        raw_ui = ui_url or (UI_URL_FILE.read_text(encoding="utf-8") if UI_URL_FILE.is_file() else "")
        raw_api = api_url or (API_URL_FILE.read_text(encoding="utf-8") if API_URL_FILE.is_file() else "")
        ui = _clean_url(raw_ui)
        api = _clean_url(raw_api)
    except ValueError as exc:
        return False, str(exc)
    if not ui or not api:
        return False, "missing stored public URLs"
    if not fetch_ok(ui + "/"):
        return False, f"UI tunnel unreachable: {ui}"
    if not fetch_ok(api + "/api/settings/health"):
        return False, f"API tunnel unreachable: {api}"
    return True, "ok"


def load_last_notified() -> dict[str, str]:
    if not STATE_FILE.is_file():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def save_last_notified(ui_url: str, api_url: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"ui": ui_url, "api": api_url}, indent=2) + "\n")


def urls_changed(ui_url: str, api_url: str) -> bool:
    last = load_last_notified()
    return last.get("ui") != ui_url or last.get("api") != api_url


def send_email(subject: str, body: str, env: dict[str, str] | None = None) -> None:
    c = smtp_config(env)
    if not c["user"] or not c["password"] or not c["notify"]:
        raise RuntimeError("SMTP not configured (need SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL in .env)")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = c["user"]
    msg["To"] = c["notify"]
    msg.set_content(body)

    port = int(c["port"])
    context = ssl.create_default_context()
    with smtplib.SMTP(c["host"], port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(c["user"], c["password"])
        server.send_message(msg)


def format_tunnel_body(ui_url: str, api_url: str, reason: str = "") -> str:
    lines = [
        "UML Pipeline public tunnel URLs",
        "",
        f"Browser UI:  {ui_url}",
        f"Public API:  {api_url}",
        f"API docs:    {api_url.rstrip('/')}/docs",
        "",
        "Local services (Streamlit→API): http://127.0.0.1:8000",
    ]
    if reason:
        lines.extend(["", f"Reason: {reason}"])
    lines.extend(
        [
            "",
            "Cloudflare quick-tunnel URLs change when tunnels are recreated.",
            "Monitor: bash scripts/monitor_public_tunnels.sh --loop",
        ]
    )
    return "\n".join(lines)


def publish_urls(ui_url: str, api_url: str, reason: str = "", force_email: bool = False) -> bool:
    """Update .env/url/Link files and email if URLs changed. Returns True if email was sent."""
    ui_url = _clean_url(ui_url)
    api_url = _clean_url(api_url)
    update_env_urls(ui_url, api_url)
    env = load_env()
    changed = urls_changed(ui_url, api_url)
    if not configured(env):
        print("SMTP not configured — Link/.env updated, email skipped")
        save_last_notified(ui_url, api_url)
        return False
    if not changed and not force_email:
        print("URLs unchanged — Link refreshed, email skipped")
        return False
    try:
        send_email(
            "UML Pipeline: public tunnel URLs updated",
            format_tunnel_body(ui_url, api_url, reason),
            env,
        )
    except Exception as exc:
        print(f"SMTP not sent: {exc}")
        save_last_notified(ui_url, api_url)
        return False
    save_last_notified(ui_url, api_url)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish tunnel URLs and notify")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pub = sub.add_parser("publish", help="Update .env and email if URLs changed")
    p_pub.add_argument("--ui", required=True)
    p_pub.add_argument("--api", required=True)
    p_pub.add_argument("--reason", default="")
    p_pub.add_argument("--force-email", action="store_true")

    p_urls = sub.add_parser("urls", help="Email tunnel URLs (no .env update)")
    p_urls.add_argument("--ui", required=True)
    p_urls.add_argument("--api", required=True)
    p_urls.add_argument("--reason", default="")
    p_urls.add_argument("--subject", default="UML Pipeline: public tunnel URLs updated")

    p_test = sub.add_parser("test", help="Send test email with current URLs")
    p_test.add_argument("--ui", default="")
    p_test.add_argument("--api", default="")

    p_raw = sub.add_parser("send", help="Send raw subject/body")
    p_raw.add_argument("--subject", required=True)
    p_raw.add_argument("--body", required=True)

    p_check = sub.add_parser("check", help="Health-check public tunnel URLs")
    p_check.add_argument("--quiet", action="store_true")

    p_sync = sub.add_parser("sync-link", help="Rewrite Link + Link.md from stored URL files")
    p_sync.add_argument("--ui", default="")
    p_sync.add_argument("--api", default="")

    args = parser.parse_args()
    env = load_env()

    try:
        if args.cmd == "check":
            ok, detail = check_tunnels()
            if args.quiet:
                return 0 if ok else 1
            if ok:
                print("Tunnels healthy")
                return 0
            print(f"Tunnels unhealthy: {detail}", file=sys.stderr)
            return 1
        if args.cmd == "sync-link":
            ui = args.ui or (UI_URL_FILE.read_text(encoding="utf-8") if UI_URL_FILE.is_file() else "")
            api = args.api or (API_URL_FILE.read_text(encoding="utf-8") if API_URL_FILE.is_file() else "")
            write_link_files(ui, api)
            print(f"Link synced UI={_clean_url(ui)} API={_clean_url(api)}")
        elif args.cmd == "publish":
            sent = publish_urls(args.ui, args.api, args.reason, args.force_email)
            print("email_sent=yes" if sent else "email_sent=no")
        elif args.cmd == "urls":
            send_email(args.subject, format_tunnel_body(args.ui, args.api, args.reason), env)
        elif args.cmd == "test":
            ui = args.ui
            api = args.api
            if not ui and (ROOT / "data/run/public_ui_url.txt").is_file():
                ui = (ROOT / "data/run/public_ui_url.txt").read_text().strip()
            if not api and (ROOT / "data/run/public_api_url.txt").is_file():
                api = (ROOT / "data/run/public_api_url.txt").read_text().strip()
            ui = ui or "(not set)"
            api = api or "(not set)"
            send_email(
                "UML Pipeline: tunnel email test",
                format_tunnel_body(ui, api, reason="Test email — SMTP configuration OK"),
                env,
            )
        else:
            send_email(args.subject, args.body, env)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
