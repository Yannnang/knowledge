"""从飞书通讯录拉取组织现状并归一化（BFS 部门树 + 按部门取用户）。

契约映射（MYIT-10 v1.0 §2/§3）：
- dept_id ≡ 飞书 open_department_id（v1 同值，单列 feishu_dept_id 以备换源）；
- 主部门 = 用户 department_ids[0]（飞书惯例首位为主部门；实体缺该字段时回退为抓取部门）；
- union_id 缺失 → 硬失败（契约主键依赖它，多为通讯录 scope 未授权）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger("orgsync.snapshot")

ROOT_DEPT_ID = "0"


class SnapshotError(RuntimeError):
    """通讯录数据不满足契约前提。"""


class ContactClient(Protocol):
    def list_child_departments(self, department_id: str) -> list[dict[str, Any]]: ...
    def list_department_users(self, department_id: str) -> list[dict[str, Any]]: ...


@dataclass
class OrgState:
    """归一化后的组织现状（当日飞书侧真值，未含拉链）。"""

    departments: dict[str, dict[str, Any]]  # dept_id -> {name, parent_dept_id, dept_level, dept_path}
    users: dict[str, dict[str, Any]]        # user_id(=union_id) -> {name, feishu_open_id, feishu_user_id, primary_dept_id, email}


def fetch_org_state(client: ContactClient) -> OrgState:
    departments = _fetch_departments(client)
    _derive_level_and_path(departments)
    users = _fetch_users(client, set(departments))
    return OrgState(departments=departments, users=users)


def _fetch_departments(client: ContactClient) -> dict[str, dict[str, Any]]:
    departments: dict[str, dict[str, Any]] = {}
    queue = [ROOT_DEPT_ID]
    while queue:
        current = queue.pop(0)
        for item in client.list_child_departments(current):
            od = item.get("open_department_id")
            if not od or od in departments:
                continue
            parent = item.get("parent_department_id") or None
            departments[od] = {
                "name": item.get("name") or "",
                "parent_dept_id": None if parent in (None, ROOT_DEPT_ID) else parent,
            }
            queue.append(od)
    return departments


def _derive_level_and_path(departments: dict[str, dict[str, Any]]) -> None:
    """dept_level：根=1；dept_path：内部 id 物化路径 /{根}/…/{自身}/。带环检测。"""

    def resolve(dept_id: str, stack: tuple[str, ...]) -> tuple[int, str]:
        dept = departments[dept_id]
        if "dept_level" in dept:
            return dept["dept_level"], dept["dept_path"]
        if dept_id in stack:
            raise SnapshotError(f"部门树出现环：{' -> '.join(stack + (dept_id,))}")
        parent = dept["parent_dept_id"]
        if parent is None or parent not in departments:
            level, path = 1, f"/{dept_id}/"
        else:
            parent_level, parent_path = resolve(parent, stack + (dept_id,))
            level, path = parent_level + 1, f"{parent_path}{dept_id}/"
        dept["dept_level"] = level
        dept["dept_path"] = path
        return level, path

    for dept_id in departments:
        resolve(dept_id, ())


def _fetch_users(client: ContactClient, known_departments: set[str]) -> dict[str, dict[str, Any]]:
    users: dict[str, dict[str, Any]] = {}
    for od in sorted(known_departments):
        for item in client.list_department_users(od):
            union_id = item.get("union_id")
            open_id = item.get("open_id") or ""
            if not union_id:
                raise SnapshotError(
                    f"通讯录用户缺少 union_id（open_id={open_id!r}）："
                    "契约主键依赖 union_id，请检查自建应用通讯录授权范围"
                )
            if not open_id:
                raise SnapshotError(f"用户 {union_id} 缺少 open_id，契约要求 feishu_open_id 非空")
            if union_id in users:
                # 多部门成员去重：主部门以首次抓取为准，但可空字段用后续出现补全
                existing = users[union_id]
                if not existing.get("feishu_user_id"):
                    existing["feishu_user_id"] = item.get("user_id") or None
                if not existing.get("email"):
                    existing["email"] = item.get("enterprise_email") or item.get("email") or None
                continue
            dept_ids = item.get("department_ids") or [od]
            primary = dept_ids[0] if dept_ids else None
            if primary is not None and primary not in known_departments:
                log.warning("用户 %s 的主部门 %s 不在部门树内，primary_dept_id 置 NULL", union_id, primary)
                primary = None
            users[union_id] = {
                "name": item.get("name") or "",
                "feishu_open_id": open_id,
                "feishu_user_id": item.get("user_id") or None,
                "primary_dept_id": primary,
                "email": item.get("enterprise_email") or item.get("email") or None,
            }
    return users
