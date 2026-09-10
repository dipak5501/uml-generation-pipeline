#!/usr/bin/env python3
"""Write reports/RQ3_PACKAGE_FAILURE_CHAPTER.md from the live SQLite database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.db import get_engine, init_db
    from app.services.package_failures import (
        format_package_failure_chapter,
        package_failure_report,
    )
    from sqlmodel import Session

    init_db()
    out_md = ROOT / "reports" / "RQ3_PACKAGE_FAILURE_CHAPTER.md"
    out_json = ROOT / "reports" / "RQ3_PACKAGE_FAILURE_CHAPTER.json"
    with Session(get_engine()) as session:
        report = package_failure_report(session)
    out_md.write_text(format_package_failure_chapter(report), encoding="utf-8")
    out_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out_md}")
    print(f"Wrote {out_json}")
    print(
        f"packages={report.get('package_total')} failures={report.get('package_failures')} "
        f"repair_attempts={((report.get('repair') or {}).get('repair_attempts'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
