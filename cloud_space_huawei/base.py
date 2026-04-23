"""子模块基类 — 共享 session / headers / 重试逻辑"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("cloud-space-huawei")

Result = Dict[str, Any]


class BaseModule:
    """所有子模块的基类，提供公共的 HTTP 请求能力"""

    BASE_URL = "https://cloud.huawei.com"

    def __init__(
        self,
        session: requests.Session,
        csrf_token: str,
        user_id: str,
        device_id: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self._session = session
        self._csrf_token = csrf_token
        self._user_id = user_id
        self._device_id = device_id
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._start_cursor: str = "0"

    # ---------- 子类可覆盖 ----------

    def _headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "csrftoken": self._csrf_token,
            "userid": self._user_id,
            "x-hw-account-brand-id": "0",
            "x-hw-app-brand-id": "1",
            "x-hw-client-mode": "frontend",
            "x-hw-device-brand": "HUAWEI",
            "x-hw-device-category": "Web",
            "x-hw-device-id": self._device_id,
            "x-hw-device-manufacturer": "HUAWEI",
            "x-hw-device-type": "7",
            "x-hw-os-brand": "Web",
            "referer": "https://cloud.huawei.com/home",
            "origin": "https://cloud.huawei.com",
        }

    # ---------- 内部工具 ----------

    @staticmethod
    def _get_code(data: Dict[str, Any]) -> str:
        if "code" in data:
            return str(data["code"])
        return str(data.get("Result", {}).get("code", ""))

    def _update_start_cursor(self, data: Dict[str, Any]) -> None:
        cursor = data.get("startCursor", "")
        if cursor:
            self._start_cursor = str(cursor)

    def _sync_cookies(self, resp: requests.Response) -> None:
        """从响应同步关键 cookie"""
        jar = self._session.cookies
        for name in ["CSRFToken", "shareToken", "JSESSIONID"]:
            value = jar.get(name, domain="cloud.huawei.com")
            if value and name == "CSRFToken":
                self._csrf_token = value

    # ---------- HTTP 请求 ----------

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        last_exc: Optional[requests.RequestException] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.request(method, url, **kwargs)
                return resp
            except (requests.ConnectionError, requests.Timeout, requests.RequestException) as e:
                last_exc = e
                logger.warning("请求失败 (第%d/%d次): %s", attempt, self._max_retries, e)
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)
        raise last_exc  # type: ignore[misc]

    def _post(
        self,
        url: str,
        body: Dict[str, Any],
        trace_prefix: str = "03135",
        timeout: int = 30,
    ) -> Dict[str, Any]:
        if "traceId" not in body:
            body["traceId"] = _generate_traceid(trace_prefix)
        try:
            resp = self._request_with_retry(
                "POST", url, headers=self._headers(), json=body, timeout=timeout, verify=False,
            )
            self._sync_cookies(resp)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                return {"error": "认证失败(401)，cookies 已过期", "_code": "401"}
            return {"error": f"HTTP {resp.status_code}", "_code": str(resp.status_code)}
        except requests.RequestException as e:
            return {"error": "请求异常", "detail": str(e), "_code": "-1"}
        except json.JSONDecodeError as e:
            return {"error": "响应解析失败", "detail": str(e), "_code": "-2"}

    def _get(
        self,
        url: str,
        trace_prefix: str = "03135",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            resp = self._request_with_retry(
                "GET", url, headers=self._headers(), params=params, timeout=30, verify=False,
            )
            self._sync_cookies(resp)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                return {"error": "认证失败(401)，cookies 已过期", "_code": "401"}
            return {"error": f"HTTP {resp.status_code}", "_code": str(resp.status_code)}
        except requests.RequestException as e:
            return {"error": "请求异常", "detail": str(e), "_code": "-1"}
        except json.JSONDecodeError as e:
            return {"error": "响应解析失败", "detail": str(e), "_code": "-2"}


def _generate_traceid(prefix: str = "03135") -> str:
    import random
    random_part = ''.join(str(random.randint(1, 9)) for _ in range(8))
    return f"{prefix}_02_{int(time.time())}_{random_part}"
