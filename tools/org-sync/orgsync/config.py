"""环境配置。约束：凭据只走环境变量，严禁硬编码（仓库红线）。"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """配置缺失或非法。"""


@dataclass(frozen=True)
class Config:
    app_id: str
    app_secret: str
    base_url: str
    output_dir: str
    state_dir: str
    timezone: str = "Asia/Shanghai"

    @property
    def masked_app_id(self) -> str:
        return self.app_id[:4] + "***" if len(self.app_id) > 4 else "***"


def load_config(env: Mapping[str, str] | None = None) -> Config:
    e: Mapping[str, str] = os.environ if env is None else env
    app_id = (e.get("FEISHU_APP_ID") or "").strip()
    app_secret = (e.get("FEISHU_APP_SECRET") or "").strip()
    if not app_id or not app_secret:
        raise ConfigError(
            "缺少 FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量"
            "（凭据只允许环境变量注入，禁止写入代码或仓库）"
        )
    return Config(
        app_id=app_id,
        app_secret=app_secret,
        base_url=(e.get("FEISHU_BASE_URL") or "https://open.feishu.cn").rstrip("/"),
        output_dir=e.get("ORG_SYNC_OUTPUT_DIR") or "./output",
        state_dir=e.get("ORG_SYNC_STATE_DIR") or "./state",
        timezone=e.get("ORG_SYNC_TIMEZONE") or "Asia/Shanghai",
    )
