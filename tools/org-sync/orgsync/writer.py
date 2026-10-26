"""dt 分区写出与状态滚动。

产物布局（契约 v1.0 §1）：
    {output_dir}/dt={YYYY-MM-DD}/org_department.jsonl
    {output_dir}/dt={YYYY-MM-DD}/org_user.jsonl
    {output_dir}/dt={YYYY-MM-DD}/manifest.json
状态（供次日拉链比较）：
    {state_dir}/latest.json = {as_of, departments: [...], users: [...]}

写文件一律先写 .tmp 再 os.replace，避免半份快照被下游读到。
"""
from __future__ import annotations

import json
import os
from typing import Any

FAR_FUTURE = "9999-12-31"


def _atomic_write(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n" for r in rows)


def write_snapshot(
    output_dir: str,
    dt: str,
    dept_rows: list[dict[str, Any]],
    user_rows: list[dict[str, Any]],
    meta: dict[str, Any],
) -> str:
    partition = os.path.join(output_dir, f"dt={dt}")
    os.makedirs(partition, exist_ok=True)
    _atomic_write(os.path.join(partition, "org_department.jsonl"), _jsonl(dept_rows))
    _atomic_write(os.path.join(partition, "org_user.jsonl"), _jsonl(user_rows))
    open_dept = [r for r in dept_rows if r["valid_to"] == FAR_FUTURE]
    open_user = [r for r in user_rows if r["valid_to"] == FAR_FUTURE]
    manifest = {
        "dt": dt,
        **meta,
        "dept_rows_total": len(dept_rows),
        "dept_rows_open": len(open_dept),
        "dept_open_disabled": sum(1 for r in open_dept if r["status"] == "disabled"),
        "user_rows_total": len(user_rows),
        "user_rows_open": len(open_user),
        "user_open_departed": sum(1 for r in open_user if r["employment_status"] == "departed"),
    }
    _atomic_write(os.path.join(partition, "manifest.json"), json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return partition


def save_state(state_dir: str, dt: str, dept_rows: list[dict[str, Any]], user_rows: list[dict[str, Any]]) -> None:
    os.makedirs(state_dir, exist_ok=True)
    payload = {"as_of": dt, "departments": dept_rows, "users": user_rows}
    _atomic_write(os.path.join(state_dir, "latest.json"), json.dumps(payload, ensure_ascii=False))


def load_state(state_dir: str) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    path = os.path.join(state_dir, "latest.json")
    if not os.path.exists(path):
        return None, [], []
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("as_of"), payload.get("departments") or [], payload.get("users") or []
