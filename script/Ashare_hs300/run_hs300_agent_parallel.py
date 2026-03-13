#!/usr/bin/env python3

from __future__ import annotations

import csv
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path("/Users/bytedance_1/trae_cn/nanobot")
CSV_PATH = REPO_ROOT / "script" / "Ashare_hs300" / "hs300_stocks_list.csv"
OUTPUT_DIR = REPO_ROOT / "script" / "Ashare_hs300" / date.today().isoformat()

MAX_WORKERS = 2
CONTINUE_ON_ERROR = True
DRY_RUN = False

AGENT_SESSION_ID = "cli:direct"
AGENT_WORKSPACE = "/Users/bytedance_1/trae_cn/nanobot_record/.nanobot/workspace/Ashare/"
AGENT_CONFIG_PATH: str | None = None
AGENT_MARKDOWN = True
AGENT_LOGS = True

DEFAULT_TEMPLATE = (
    "使用skill - ashare-trader 来分析 股票代码：{stock_code} - 股票名称：{stock_name}。\n"
    "最终将分析的结果写入到md里去，md的文件名为{stock_code}-{stock_name}，存储路径为{output_dir}\n"
)


@dataclass(frozen=True)
class StockRow:
    stock_code: str
    stock_name: str


@dataclass(frozen=True)
class RunConfig:
    session_id: str
    workspace: str | None
    config_path: str | None
    markdown: bool
    logs: bool
    dry_run: bool
    output_dir: str


def load_hs300_rows(csv_path: Path) -> list[StockRow]:
    if not csv_path.exists():
        raise FileNotFoundError(str(csv_path))

    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV缺少表头")
        if "股票代码" not in reader.fieldnames or "股票名称" not in reader.fieldnames:
            raise ValueError(f"CSV表头不符合预期：{reader.fieldnames}")

        rows: list[StockRow] = []
        for item in reader:
            code = (item.get("股票代码") or "").strip()
            name = (item.get("股票名称") or "").strip()
            if code and name:
                rows.append(StockRow(stock_code=code, stock_name=name))
        return rows

def _render_prompt_with_output_dir(template: str, row: StockRow, output_dir: str) -> str:
    mapping = {
        "stock_code": row.stock_code,
        "stock_name": row.stock_name,
        "code": row.stock_code,
        "name": row.stock_name,
        "output_dir": output_dir,
    }
    return template.format_map(mapping)


def _run_one(row: StockRow, template: str, cfg: RunConfig) -> tuple[str, str, str]:
    prompt = _render_prompt_with_output_dir(template, row, cfg.output_dir)
    if cfg.dry_run:
        return row.stock_code, row.stock_name, prompt

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from nanobot.cli.commands import agent as agent_command

    agent_command(
        message=prompt,
        session_id=cfg.session_id,
        workspace=cfg.workspace,
        config=cfg.config_path,
        markdown=cfg.markdown,
        logs=cfg.logs,
    )
    return row.stock_code, row.stock_name, "ok"


def _build_run_config() -> RunConfig:
    return RunConfig(
        session_id=AGENT_SESSION_ID,
        workspace=AGENT_WORKSPACE,
        config_path=AGENT_CONFIG_PATH,
        markdown=AGENT_MARKDOWN,
        logs=AGENT_LOGS,
        dry_run=DRY_RUN,
        output_dir=str(OUTPUT_DIR),
    )

def run_all() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    template = DEFAULT_TEMPLATE
    rows = load_hs300_rows(CSV_PATH)
    cfg = _build_run_config()

    failures: list[tuple[str, str, str]] = []
    rendered_prompts: list[tuple[str, str, str]] = []

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_run_one, row, template, cfg): row for row in rows}
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                rendered_prompts.append(fut.result())
            except BaseException as e:
                failures.append((row.stock_code, row.stock_name, str(e)))
                traceback.print_exc()
                if not CONTINUE_ON_ERROR:
                    for other in futures:
                        other.cancel()
                    break

    if cfg.dry_run:
        for stock_code, stock_name, rendered in rendered_prompts:
            sys.stdout.write("\n")
            sys.stdout.write(f"[{stock_code} {stock_name}]\n")
            sys.stdout.write(rendered)
            sys.stdout.write("\n")

    if failures:
        sys.stderr.write("\nFailed stocks:\n")
        for stock_code, stock_name, err in failures:
            sys.stderr.write(f"  - {stock_code} {stock_name}: {err}\n")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
