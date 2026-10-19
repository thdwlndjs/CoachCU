from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.storage import SQLiteRepository
from app.services.startup import set_run_on_login, set_run_on_unlock
from app.ui.main_window import run_app


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Personal Work Coach")
    parser.add_argument("--trigger", choices=["manual", "login", "unlock"], default="manual")
    parser.add_argument("--minimized", action="store_true")
    parser.add_argument("--db", default=None, help="SQLite database path override")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repository = SQLiteRepository(args.db)
    policy = repository.get_policy()
    try:
        set_run_on_login(policy.run_on_login)
        set_run_on_unlock(policy.run_on_unlock)
    except OSError as exc:
        print(f"Windows startup integration could not be configured: {exc}", file=sys.stderr)
    return run_app(repository, trigger=args.trigger, minimized=args.minimized)


if __name__ == "__main__":
    raise SystemExit(main())
