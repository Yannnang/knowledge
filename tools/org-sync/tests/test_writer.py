"""写出/状态滚动 + 配置测试。"""
import json

import pytest

from orgsync.config import ConfigError, load_config
from orgsync.writer import load_state, save_state, write_snapshot
from orgsync.zipper import FAR_FUTURE

DT = "2026-10-26"


def test_write_snapshot_layout_and_manifest(tmp_path):
    depts = [{"dept_id": "od1", "name": "技术部", "status": "active",
              "valid_from": DT, "valid_to": FAR_FUTURE, "synced_at": "s"}]
    users = [{"user_id": "u1", "name": "张三", "employment_status": "active",
              "valid_from": DT, "valid_to": FAR_FUTURE, "synced_at": "s"},
             {"user_id": "u2", "name": "李四", "employment_status": "departed",
              "valid_from": DT, "valid_to": FAR_FUTURE, "synced_at": "s"}]
    out = write_snapshot(str(tmp_path), DT, depts, users,
                         {"synced_at": "2026-10-26T02:00:00Z", "contract": "MYIT-10 组织档案数据契约 v1.0"})
    assert out.endswith(f"dt={DT}")
    with open(tmp_path / f"dt={DT}" / "org_department.jsonl", encoding="utf-8") as f:
        assert json.loads(f.readline())["name"] == "技术部"  # UTF-8 中文原样
    manifest = json.loads((tmp_path / f"dt={DT}" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dept_rows_open"] == 1
    assert manifest["user_open_departed"] == 1
    assert manifest["contract"] == "MYIT-10 组织档案数据契约 v1.0"


def test_state_roundtrip(tmp_path):
    rows = [{"dept_id": "od1", "valid_to": FAR_FUTURE}]
    save_state(str(tmp_path), DT, rows, [])
    as_of, depts, users = load_state(str(tmp_path / "nonexistent"))
    assert as_of is None and depts == [] and users == []
    as_of, depts, users = load_state(str(tmp_path))
    assert as_of == DT and depts == rows and users == []


def test_load_config_requires_credentials():
    with pytest.raises(ConfigError):
        load_config(env={})
    cfg = load_config(env={"FEISHU_APP_ID": "cli_abc123", "FEISHU_APP_SECRET": "s3cret"})
    assert cfg.masked_app_id == "cli_***"
    assert cfg.base_url == "https://open.feishu.cn"
    assert "s3cret" not in repr(cfg.masked_app_id)
