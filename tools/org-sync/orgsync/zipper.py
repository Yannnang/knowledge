"""拉链（SCD2）合并：前日全量表 + 当日飞书现状 → 当日全量表。纯函数，无 I/O。

契约语义（MYIT-10 v1.0）：
- 每份 dt 快照 = 完整拉链表（含历史闭行）；valid_to == FAR_FUTURE 表示当前有效；
- 部门：name/parent_dept_id/dept_level/dept_path/status 任一变更 → 闭旧行（valid_to=今日-1）开新行（valid_from=今日）；
  从通讯录消失 → active 行闭合，开 disabled 行（不物理删除）；重新出现 → 反向；
- 人员：仅 primary_dept_id / employment_status 变更触发拉链；
  name/email/feishu_open_id/feishu_user_id 为现值语义，在开行上原位更新；
  从通讯录消失 → employment_status=departed + departed_at=首次发现时刻（保留末次 primary_dept_id）；
  复职（departed 行仍开但人回来了）→ 闭 departed 行开 active 行；
- 同日重跑修正：旧开行 valid_from >= 今日时直接替换该行，不产生非法区间（幂等）。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

FAR_FUTURE = "9999-12-31"

_DEPT_TRACKED = ("name", "parent_dept_id", "dept_level", "dept_path", "status")
_DEPT_IN_PLACE = ("name", "parent_dept_id", "dept_level", "dept_path")
_USER_TRACKED = ("primary_dept_id", "employment_status")
_USER_IN_PLACE = ("name", "feishu_open_id", "feishu_user_id", "email")


def shift_day(day: str, delta: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=delta)).isoformat()


def _split_open(rows: list[dict[str, Any]], key: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """拆出历史闭行（原样保留）与开行索引。"""
    closed: list[dict[str, Any]] = []
    open_by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("valid_to") == FAR_FUTURE:
            open_by_key[row[key]] = dict(row)
        else:
            closed.append(dict(row))
    return closed, open_by_key


def merge_departments(
    prev_rows: list[dict[str, Any]],
    current: dict[str, dict[str, Any]],
    today: str,
    synced_at: str,
) -> list[dict[str, Any]]:
    yesterday = shift_day(today, -1)
    out, open_by_id = _split_open(prev_rows, "dept_id")

    def new_row(dept_id: str, values: dict[str, Any], valid_from: str, status: str) -> dict[str, Any]:
        return {
            "dept_id": dept_id,
            "name": values["name"],
            "parent_dept_id": values["parent_dept_id"],
            "dept_level": values["dept_level"],
            "dept_path": values["dept_path"],
            "feishu_dept_id": dept_id,  # v1 契约：与 dept_id 同值
            "status": status,
            "valid_from": valid_from,
            "valid_to": FAR_FUTURE,
            "synced_at": synced_at,
        }

    for dept_id in sorted(current):
        values = current[dept_id]
        prev = open_by_id.pop(dept_id, None)
        if prev is None:
            out.append(new_row(dept_id, values, today, "active"))
            continue
        changed = any(prev.get(k) != values.get(k) for k in _DEPT_IN_PLACE) or prev.get("status") != "active"
        if not changed:
            prev.update({k: values[k] for k in _DEPT_IN_PLACE})
            prev["synced_at"] = synced_at
            out.append(prev)
            continue
        if prev["valid_from"] >= today:  # 同日修正：替换而非叠加
            out.append(new_row(dept_id, values, prev["valid_from"], "active"))
            continue
        prev["valid_to"] = yesterday
        prev["synced_at"] = synced_at
        out.append(prev)
        out.append(new_row(dept_id, values, today, "active"))

    for dept_id in sorted(open_by_id):  # 剩余的 = 从通讯录消失的部门
        prev = open_by_id[dept_id]
        prev["synced_at"] = synced_at
        if prev.get("status") == "disabled":
            out.append(prev)  # 已裁撤，维持现状
            continue
        if prev["valid_from"] >= today:  # 当日建当日撤：直接替换为 disabled 行
            out.append(new_row(dept_id, prev, prev["valid_from"], "disabled"))
            continue
        prev["valid_to"] = yesterday
        out.append(prev)
        out.append(new_row(dept_id, prev, today, "disabled"))

    return out


def merge_users(
    prev_rows: list[dict[str, Any]],
    current: dict[str, dict[str, Any]],
    today: str,
    synced_at: str,
) -> list[dict[str, Any]]:
    yesterday = shift_day(today, -1)
    out, open_by_id = _split_open(prev_rows, "user_id")

    def new_row(user_id: str, values: dict[str, Any], valid_from: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "name": values["name"],
            "feishu_union_id": user_id,  # v1 契约：user_id ≡ 首次入库 union_id
            "feishu_open_id": values["feishu_open_id"],
            "feishu_user_id": values.get("feishu_user_id"),
            "primary_dept_id": values.get("primary_dept_id"),
            "email": values.get("email"),
            "employment_status": values["employment_status"],
            "departed_at": values.get("departed_at"),
            "valid_from": valid_from,
            "valid_to": FAR_FUTURE,
            "synced_at": synced_at,
        }

    for user_id in sorted(current):
        values = {**current[user_id], "employment_status": "active", "departed_at": None}
        prev = open_by_id.pop(user_id, None)
        if prev is None:
            out.append(new_row(user_id, values, today))
            continue
        tracked_changed = any(prev.get(k) != values.get(k) for k in _USER_TRACKED)
        if not tracked_changed:  # 现值字段原位更新，不动拉链
            prev.update({k: values.get(k) for k in _USER_IN_PLACE})
            prev["synced_at"] = synced_at
            out.append(prev)
            continue
        if prev["valid_from"] >= today:  # 同日修正（含复职当日往返）
            out.append(new_row(user_id, values, prev["valid_from"]))
            continue
        prev["valid_to"] = yesterday
        prev["synced_at"] = synced_at
        out.append(prev)
        out.append(new_row(user_id, values, today))

    for user_id in sorted(open_by_id):  # 剩余的 = 从通讯录消失（离职判定）
        prev = open_by_id[user_id]
        prev["synced_at"] = synced_at
        if prev.get("employment_status") == "departed":
            out.append(prev)  # 已离职，departed_at 保持首次发现时刻
            continue
        if prev["valid_from"] >= today:
            replaced = new_row(
                user_id,
                {**prev, "employment_status": "departed", "departed_at": synced_at},
                prev["valid_from"],
            )
            out.append(replaced)
            continue
        prev["valid_to"] = yesterday
        out.append(prev)
        out.append(
            new_row(
                user_id,
                {**prev, "employment_status": "departed", "departed_at": synced_at},
                today,
            )
        )

    return out
