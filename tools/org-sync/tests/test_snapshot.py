"""通讯录拉取与归一化测试（FakeClient，无网络）。"""
import pytest

from orgsync.snapshot import SnapshotError, fetch_org_state


class FakeClient:
    """按 {父部门: [子部门实体]} 与 {部门: [用户实体]} 提供数据。"""

    def __init__(self, dept_tree, users_by_dept):
        self.dept_tree = dept_tree
        self.users_by_dept = users_by_dept
        self.user_calls = []

    def list_child_departments(self, department_id):
        return self.dept_tree.get(department_id, [])

    def list_department_users(self, department_id):
        self.user_calls.append(department_id)
        return self.users_by_dept.get(department_id, [])


def d(od, name, parent):
    return {"open_department_id": od, "name": name, "parent_department_id": parent}


def u(union_id, name, dept_ids, **kw):
    return {"union_id": union_id, "open_id": f"ou_{union_id}", "name": name,
            "department_ids": dept_ids, **kw}


TREE = {
    "0": [d("od_root", "某公司", "0")],
    "od_root": [d("od_tech", "技术部", "od_root"), d("od_hr", "人事部", "od_root")],
    "od_tech": [d("od_backend", "后端组", "od_tech")],
}


def test_tree_levels_and_paths():
    client = FakeClient(TREE, {})
    state = fetch_org_state(client)
    assert set(state.departments) == {"od_root", "od_tech", "od_hr", "od_backend"}
    root = state.departments["od_root"]
    assert root["dept_level"] == 1 and root["dept_path"] == "/od_root/" and root["parent_dept_id"] is None
    backend = state.departments["od_backend"]
    assert backend["dept_level"] == 3
    assert backend["dept_path"] == "/od_root/od_tech/od_backend/"
    assert backend["parent_dept_id"] == "od_tech"


def test_users_dedup_and_primary_dept():
    users_by_dept = {
        "od_tech": [u("un_z", "张三", ["od_tech", "od_hr"], user_id="eid_z", enterprise_email="z@corp.com")],
        "od_hr": [u("un_z", "张三", ["od_tech", "od_hr"]), u("un_l", "李四", ["od_hr"])],
        "od_backend": [],
        "od_root": [],
    }
    state = fetch_org_state(FakeClient(TREE, users_by_dept))
    assert set(state.users) == {"un_z", "un_l"}
    z = state.users["un_z"]
    assert z["primary_dept_id"] == "od_tech"  # department_ids[0]，跨部门抓取去重
    assert z["feishu_user_id"] == "eid_z" and z["email"] == "z@corp.com"
    assert state.users["un_l"]["primary_dept_id"] == "od_hr"


def test_primary_dept_falls_back_to_fetch_dept():
    users = {"od_hr": [{"union_id": "un_x", "open_id": "ou_x", "name": "王五"}]}  # 无 department_ids
    state = fetch_org_state(FakeClient(TREE, users))
    assert state.users["un_x"]["primary_dept_id"] == "od_hr"


def test_primary_dept_outside_tree_becomes_null():
    users = {"od_hr": [u("un_y", "赵六", ["od_ghost"])]}
    state = fetch_org_state(FakeClient(TREE, users))
    assert state.users["un_y"]["primary_dept_id"] is None


def test_missing_union_id_hard_fails():
    users = {"od_hr": [{"open_id": "ou_n", "name": "无union"}]}
    with pytest.raises(SnapshotError, match="union_id"):
        fetch_org_state(FakeClient(TREE, users))


def test_missing_open_id_hard_fails():
    users = {"od_hr": [{"union_id": "un_n", "name": "无open"}]}
    with pytest.raises(SnapshotError, match="open_id"):
        fetch_org_state(FakeClient(TREE, users))
