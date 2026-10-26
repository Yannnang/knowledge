"""飞书开放平台最小客户端：tenant_access_token + 通讯录 v3（部门 BFS / 按部门取用户）。

- 仅依赖 requests；
- 网络错误与 429/5xx 自动重试（指数退避，最多 3 次）；
- 业务 code != 0 抛 FeishuAPIError；错误信息不回显 app_secret。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

import requests

log = logging.getLogger("orgsync.feishu")

RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
PAGE_SIZE = 50


class FeishuAPIError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


class FeishuClient:
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn",
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._base = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._sleep = sleep
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # -- 认证 --

    def tenant_access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        data = self._request_json(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            json_body={"app_id": self._app_id, "app_secret": self._app_secret},
            auth=False,
        )
        self._token = data["tenant_access_token"]
        self._token_expires_at = time.time() + int(data.get("expire", 7200))
        return self._token

    # -- 通讯录 v3 --

    def list_child_departments(self, department_id: str) -> list[dict[str, Any]]:
        """直接子部门（不含孙级）；调用方负责 BFS。"""
        return self._paged(
            "GET",
            f"/open-apis/contact/v3/departments/{department_id}/children",
            params={"department_id_type": "open_department_id", "page_size": PAGE_SIZE},
        )

    def list_department_users(self, department_id: str) -> list[dict[str, Any]]:
        return self._paged(
            "GET",
            "/open-apis/contact/v3/users/find_by_department",
            params={
                "department_id": department_id,
                "department_id_type": "open_department_id",
                "user_id_type": "user_id",
                "page_size": PAGE_SIZE,
            },
        )

    # -- 内部 --

    def _paged(self, method: str, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            query = dict(params)
            if page_token:
                query["page_token"] = page_token
            data = self._request_json(method, path, params=query)
            items.extend(data.get("items") or [])
            if not data.get("has_more"):
                return items
            page_token = data.get("page_token")

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        url = self._base + path
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            headers = {}
            if auth:
                headers["Authorization"] = "Bearer " + self.tenant_access_token()
            try:
                resp = self._session.request(
                    method, url, params=params, json=json_body, headers=headers, timeout=30
                )
            except requests.RequestException as exc:
                last_error = exc
                log.warning("%s %s 网络异常（第 %d/%d 次）：%s", method, path, attempt, MAX_ATTEMPTS, exc)
                self._sleep(float(2 ** (attempt - 1)))
                continue
            if resp.status_code in RETRY_STATUS:
                last_error = FeishuAPIError(f"HTTP {resp.status_code}", status=resp.status_code)
                log.warning("%s %s HTTP %d（第 %d/%d 次），退避重试", method, path, resp.status_code, attempt, MAX_ATTEMPTS)
                self._sleep(float(2 ** (attempt - 1)))
                continue
            if resp.status_code != 200:
                raise FeishuAPIError(
                    f"{method} {path} HTTP {resp.status_code}: {resp.text[:200]}",
                    status=resp.status_code,
                )
            body = resp.json()
            code = body.get("code", -1)
            if code != 0:
                raise FeishuAPIError(
                    f"{method} {path} 飞书返回 code={code} msg={body.get('msg')}"
                    "（权限不足请对照 README 的 scope 清单）",
                    code=code,
                    status=resp.status_code,
                )
            return body.get("data") or {}
        raise FeishuAPIError(f"{method} {path} 重试 {MAX_ATTEMPTS} 次仍失败：{last_error}")
