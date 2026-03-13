#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read a file line-by-line and execute each line via nanobot.cli.commands.agent()",
    )
    parser.add_argument("file", type=str, help="Input file path")
    parser.add_argument("--session", "-s", default="cli:direct", help="Session ID")
    parser.add_argument("--workspace", "-w", default=None, help="Workspace directory")
    parser.add_argument("--config", "-c", default=None, help="Config file path")
    parser.add_argument("--no-markdown", dest="markdown", action="store_false", help="Disable Markdown rendering")
    parser.add_argument("--logs", action="store_true", help="Enable nanobot runtime logs")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue processing remaining lines when an error occurs",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from nanobot.cli.commands import agent as agent_command

    input_path = Path(args.file).expanduser()
    if not input_path.exists():
        raise FileNotFoundError(str(input_path))

    failures: list[tuple[int, str]] = []
    with input_path.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            try:
                agent_command(
                    message=line,
                    session_id=args.session,
                    workspace=args.workspace,
                    config=args.config,
                    markdown=args.markdown,
                    logs=args.logs,
                )
            except BaseException:
                failures.append((lineno, line))
                traceback.print_exc()
                if not args.continue_on_error:
                    break

    if failures:
        sys.stderr.write("\nFailed lines:\n")
        for lineno, line in failures:
            sys.stderr.write(f"  - line {lineno}: {line}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

