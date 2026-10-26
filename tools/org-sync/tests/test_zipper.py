"""拉链合并（SCD2）单元测试 —— 契约 MYIT-10 v1.0 §2/§3/§5。"""
from orgsync.zipper import FAR_FUTURE, merge_departments, merge_users

TODAY = "2026-10-26"
YESTERDAY = "2026-10-25"
SYNCED = "2026-10-26T02:00:00Z"


def dept(did, name, parent=None, level=1, path=None):
    return {
        "name": name,
        "parent_dept_id": parent,
        "dept_level": level,
        "dept_path": path or f"/{did}/",
    }


def user(uid, name, dept_id, open_id=None, email=None):
    return {
        "name": name,
        "feishu_open_id": open_id or f"ou_{uid}",
        "feishu_user_id": None,
        "primary_dept_id": dept_id,
        "email": email,
    }


def open_rows(rows):
    return [r for r in rows if r["valid_to"] == FAR_FUTURE]


def assert_intervals_valid(rows):
    for r in rows:
        assert r["valid_from"] <= r["valid_to"], f"非法区间: {r}"


# -- 部门 --

def test_dept_initial_load():
    rows = merge_departments([], {"od1": dept("od1", "技术部")}, TODAY, SYNCED)
    assert len(rows) == 1
    r = rows[0]
    assert r["dept_id"] == r["feishu_dept_id"] == "od1"
    assert r["status"] == "active"
    assert (r["valid_from"], r["valid_to"]) == (TODAY, FAR_FUTURE)
    assert r["synced_at"] == SYNCED


def test_dept_unchanged_carries_forward_single_row():
    day1 = merge_departments([], {"od1": dept("od1", "技术部")}, YESTERDAY, SYNCED)
    day2 = merge_departments(day1, {"od1": dept("od1", "技术部")}, TODAY, SYNCED)
    assert len(day2) == 1
    assert day2[0]["valid_from"] == YESTERDAY  # 不闭行
    assert day2[0]["synced_at"] == SYNCED


def test_dept_rename_closes_and_reopens():
    day1 = merge_departments([], {"od1": dept("od1", "技术部")}, YESTERDAY, SYNCED)
    day2 = merge_departments(day1, {"od1": dept("od1", "技术研发部")}, TODAY, SYNCED)
    assert_intervals_valid(day2)
    closed = [r for r in day2 if r["valid_to"] != FAR_FUTURE]
    opened = open_rows(day2)
    assert len(closed) == 1 and closed[0]["name"] == "技术部" and closed[0]["valid_to"] == YESTERDAY
    assert len(opened) == 1 and opened[0]["name"] == "技术研发部" and opened[0]["valid_from"] == TODAY


def test_dept_reparent_is_tracked_change():
    prev = [{
        "dept_id": "od2", "name": "后端组", "parent_dept_id": None,
        "dept_level": 1, "dept_path": "/od2/", "feishu_dept_id": "od2",
        "status": "active", "valid_from": YESTERDAY, "valid_to": FAR_FUTURE, "synced_at": SYNCED,
    }]
    cur = {"od2": dept("od2", "后端组", parent="od1", level=2, path="/od1/od2/")}
    rows = merge_departments(prev, cur, TODAY, SYNCED)
    assert len(rows) == 2
    opened = open_rows(rows)
    assert opened[0]["dept_path"] == "/od1/od2/" and opened[0]["dept_level"] == 2


def test_dept_vanish_becomes_disabled_no_delete():
    day1 = merge_departments([], {"od1": dept("od1", "技术部")}, YESTERDAY, SYNCED)
    day2 = merge_departments(day1, {}, TODAY, SYNCED)
    assert_intervals_valid(day2)
    assert len(day2) == 2  # 闭行 + disabled 开行，未物理删除
    opened = open_rows(day2)
    assert len(opened) == 1 and opened[0]["status"] == "disabled" and opened[0]["valid_from"] == TODAY


def test_dept_disabled_carries_forward_without_duplicates():
    day1 = merge_departments([], {"od1": dept("od1", "技术部")}, "2026-10-24", SYNCED)
    day2 = merge_departments(day1, {}, YESTERDAY, SYNCED)
    day3 = merge_departments(day2, {}, TODAY, SYNCED)
    assert len(open_rows(day3)) == 1
    assert open_rows(day3)[0]["status"] == "disabled"
    assert len(day3) == len(day2)  # 不再新增行


def test_dept_reappears_reactivates():
    day1 = merge_departments([], {"od1": dept("od1", "技术部")}, "2026-10-24", SYNCED)
    day2 = merge_departments(day1, {}, YESTERDAY, SYNCED)
    day3 = merge_departments(day2, {"od1": dept("od1", "技术部")}, TODAY, SYNCED)
    opened = open_rows(day3)
    assert len(opened) == 1 and opened[0]["status"] == "active" and opened[0]["valid_from"] == TODAY


def test_dept_same_day_change_replaces_row():
    morning = merge_departments([], {"od1": dept("od1", "技术部")}, TODAY, SYNCED)
    evening = merge_departments(morning, {"od1": dept("od1", "技术研发部")}, TODAY, SYNCED)
    assert len(evening) == 1  # 同日修正=替换，不产生 [today, today-1] 非法区间
    assert evening[0]["name"] == "技术研发部"
    assert_intervals_valid(evening)


# -- 人员 --

def test_user_initial_and_stable_carry():
    day1 = merge_users([], {"u1": user("u1", "张三", "od1")}, YESTERDAY, SYNCED)
    assert day1[0]["user_id"] == day1[0]["feishu_union_id"] == "u1"
    assert day1[0]["employment_status"] == "active" and day1[0]["departed_at"] is None
    day2 = merge_users(day1, {"u1": user("u1", "张三", "od1")}, TODAY, SYNCED)
    assert len(day2) == 1 and day2[0]["valid_from"] == YESTERDAY


def test_user_name_change_is_in_place_no_zipper():
    day1 = merge_users([], {"u1": user("u1", "张三", "od1")}, YESTERDAY, SYNCED)
    day2 = merge_users(day1, {"u1": user("u1", "张三丰", "od1")}, TODAY, SYNCED)
    assert len(day2) == 1  # 现值语义：不触发拉链
    assert day2[0]["name"] == "张三丰"
    assert day2[0]["valid_from"] == YESTERDAY


def test_user_dept_change_zipper():
    day1 = merge_users([], {"u1": user("u1", "张三", "od1")}, YESTERDAY, SYNCED)
    day2 = merge_users(day1, {"u1": user("u1", "张三", "od2")}, TODAY, SYNCED)
    assert_intervals_valid(day2)
    closed = [r for r in day2 if r["valid_to"] != FAR_FUTURE]
    opened = open_rows(day2)
    assert closed[0]["primary_dept_id"] == "od1" and closed[0]["valid_to"] == YESTERDAY
    assert opened[0]["primary_dept_id"] == "od2" and opened[0]["valid_from"] == TODAY


def test_user_vanish_marks_departed_keeps_last_dept():
    day1 = merge_users([], {"u1": user("u1", "张三", "od1")}, YESTERDAY, SYNCED)
    day2 = merge_users(day1, {}, TODAY, SYNCED)
    assert_intervals_valid(day2)
    opened = open_rows(day2)
    assert len(opened) == 1
    assert opened[0]["employment_status"] == "departed"
    assert opened[0]["departed_at"] == SYNCED
    assert opened[0]["primary_dept_id"] == "od1"  # 保留末次主部门


def test_departed_user_departed_at_not_overwritten():
    day1 = merge_users([], {"u1": user("u1", "张三", "od1")}, "2026-10-24", SYNCED)
    day2 = merge_users(day1, {}, YESTERDAY, SYNCED)
    first_departed_at = open_rows(day2)[0]["departed_at"]
    day3 = merge_users(day2, {}, TODAY, "2026-10-26T03:00:00Z")
    opened = open_rows(day3)
    assert len(opened) == 1
    assert opened[0]["departed_at"] == first_departed_at  # 首次发现时刻，不被后续同步覆盖
    assert opened[0]["synced_at"] == "2026-10-26T03:00:00Z"


def test_user_rehire_closes_departed_opens_active():
    day1 = merge_users([], {"u1": user("u1", "张三", "od1")}, "2026-10-24", SYNCED)
    day2 = merge_users(day1, {}, YESTERDAY, SYNCED)
    day3 = merge_users(day2, {"u1": user("u1", "张三", "od1")}, TODAY, SYNCED)
    assert_intervals_valid(day3)
    opened = open_rows(day3)
    assert len(opened) == 1
    assert opened[0]["employment_status"] == "active" and opened[0]["departed_at"] is None


def test_rerun_same_day_idempotent():
    day1 = merge_users([], {"u1": user("u1", "张三", "od1")}, YESTERDAY, SYNCED)
    run_a = merge_users(day1, {"u1": user("u1", "张三", "od2")}, TODAY, SYNCED)
    run_b = merge_users(run_a, {"u1": user("u1", "张三", "od2")}, TODAY, SYNCED)
    assert len(run_b) == len(run_a)
    assert_intervals_valid(run_b)
    d1 = merge_departments([], {"od1": dept("od1", "技术部")}, YESTERDAY, SYNCED)
    r_a = merge_departments(d1, {"od1": dept("od1", "研发部")}, TODAY, SYNCED)
    r_b = merge_departments(r_a, {"od1": dept("od1", "研发部")}, TODAY, SYNCED)
    assert len(r_b) == len(r_a)
