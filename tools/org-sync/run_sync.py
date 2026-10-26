#!/usr/bin/env python3
"""org-sync 入口：飞书通讯录 → 组织档案每日全量快照（MYIT-10 契约 v1.0）。

用法：
    python run_sync.py [--date YYYY-MM-DD] [--output-dir DIR] [--state-dir DIR]

流程：读状态 → 拉飞书通讯录 → 拉链合并 → 写 dt 分区 → 滚动状态。
凭据只走环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET（见 README）。
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from orgsync.config import ConfigError, load_config
from orgsync.feishu import FeishuClient
from orgsync.snapshot import fetch_org_state
from orgsync.writer import load_state, save_state, write_snapshot
from orgsync.zipper import FAR_FUTURE, merge_departments, merge_users

log = logging.getLogger("orgsync")

_CST = timezone(timedelta(hours=8))  # Asia/Shanghai 固定偏移（避免 Windows 缺 tzdata）


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="飞书通讯录 → 组织档案每日全量快照")
    parser.add_argument("--date", help="快照分区日期 YYYY-MM-DD（默认今天，Asia/Shanghai）")
    parser.add_argument("--output-dir", help="覆盖 ORG_SYNC_OUTPUT_DIR")
    parser.add_argument("--state-dir", help="覆盖 ORG_SYNC_STATE_DIR")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)

    try:
        cfg = load_config()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    output_dir = args.output_dir or cfg.output_dir
    state_dir = args.state_dir or cfg.state_dir
    dt = args.date or datetime.now(_CST).date().isoformat()
    try:
        datetime.strptime(dt, "%Y-%m-%d")
    except ValueError:
        log.error("--date 需为 YYYY-MM-DD：%r", dt)
        return 2
    synced_at = _utc_now_iso()

    client = FeishuClient(cfg.app_id, cfg.app_secret, cfg.base_url)
    log.info("拉取飞书通讯录（app=%s）…", cfg.masked_app_id)
    state = fetch_org_state(client)
    log.info("现状：部门 %d，人员 %d", len(state.departments), len(state.users))

    as_of, prev_depts, prev_users = load_state(state_dir)
    initial = as_of is None
    if initial:
        log.info("无历史状态，按初始加载处理（全部行 valid_from=%s）", dt)
    elif as_of >= dt:
        log.info("状态 as_of=%s ≥ dt=%s，同日重跑，拉链规则将做同日替换（幂等）", as_of, dt)

    dept_rows = merge_departments(prev_depts, state.departments, dt, synced_at)
    user_rows = merge_users(prev_users, state.users, dt, synced_at)

    meta = {
        "synced_at": synced_at,
        "source": "feishu contact v3",
        "feishu_app_id": cfg.masked_app_id,
        "initial_load": initial,
        "prev_as_of": as_of,
        "contract": "MYIT-10 组织档案数据契约 v1.0",
    }
    partition = write_snapshot(output_dir, dt, dept_rows, user_rows, meta)
    save_state(state_dir, dt, dept_rows, user_rows)

    open_users = sum(1 for r in user_rows if r["valid_to"] == FAR_FUTURE and r["employment_status"] == "active")
    departed = sum(1 for r in user_rows if r["valid_to"] == FAR_FUTURE and r["employment_status"] == "departed")
    log.info("快照写出 %s：部门行 %d，人员行 %d（在职 %d / 离职 %d）", partition, len(dept_rows), len(user_rows), open_users, departed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
