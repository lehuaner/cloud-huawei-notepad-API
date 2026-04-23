"""核心客户端 — 用户入口，整合登录 + 各子模块"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional

import requests

from .auth import AuthManager, LoginResult
from .base import BaseModule, _generate_traceid

logger = logging.getLogger("cloud-space-huawei")


class HuaweiCloudClient:
    """华为云空间 Python SDK 的主入口

    用法 1 — 从账号密码登录::

        client = HuaweiCloudClient()
        result = client.login("手机号", "密码")

        if result.need_verify:
            code = input("验证码: ")
            result = client.verify_device(code)

        # 保存 cookies 供下次使用
        cookies = result.cookies

        # 使用子模块
        client.notepad.get_notes_list()

    用法 2 — 从 cookies dict 恢复会话::

        client = HuaweiCloudClient.from_cookies(cookies)

    用法 3 — 账号密码登录 + 传入已有 cookies（跳过设备验证）::

        client = HuaweiCloudClient()
        result = client.login("手机号", "密码", cookies=saved_cookies)

    属性:
        notepad: 备忘录模块
        contacts: 联系人模块
        gallery: 图库模块
        drive: 云盘模块
        find_device: 查找设备模块
    """

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.verify = False
        self._auth = AuthManager(self._session)

        # 子模块 — 懒加载
        self._notepad: Optional[Any] = None
        self._contacts: Optional[Any] = None
        self._gallery: Optional[Any] = None
        self._drive: Optional[Any] = None
        self._find_device: Optional[Any] = None

        # 从 cookies 提取的关键字段
        self._cookies_dict: Dict[str, str] = {}
        self._csrf_token: str = ''
        self._user_id: str = ''
        self._device_id: str = ''

        # 心跳保活线程
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_interval: int = 300  # 默认 5 分钟
        self._heartbeat_on_refresh: Optional[Callable[[str], None]] = None

    # ==================== 登录 API ====================

    def login(
        self,
        phone: str,
        password: str,
        cookies: Optional[Dict[str, str]] = None,
    ) -> LoginResult:
        """账号密码登录

        Args:
            phone: 手机号
            password: 密码
            cookies: 可选，之前保存的 cookies（含信任设备信息），
                     传入后可跳过新设备验证

        Returns:
            LoginResult — 检查 need_verify 判断是否需要验证码
        """
        result = self._auth.login(phone, password, cookies=cookies)
        if result.success and not result.need_verify:
            self._apply_login_result(result)
        return result

    def verify_device(self, verify_code: str) -> LoginResult:
        """提交设备验证码

        Args:
            verify_code: 设备收到的验证码

        Returns:
            LoginResult
        """
        result = self._auth.verify_device(verify_code)
        if result.success:
            self._apply_login_result(result)
        return result

    @classmethod
    def from_cookies(cls, cookies: Dict[str, str]) -> "HuaweiCloudClient":
        """从 cookies 字典恢复会话 (不经过登录)

        cookies 分为已信任和未信任两种：
        - 已信任的 cookies 可使用所有模块 (联系人、备忘录、图库、云盘、查找设备)
        - 未信任的 cookies 仅可使用查找设备，其他模块不可用

        会通过 heartbeatCheck(checkType=1) 验证会话是否有效，
        如果 cookies 已过期则抛出 RuntimeError。

        Args:
            cookies: cookies 字典

        Returns:
            HuaweiCloudClient 实例

        Raises:
            RuntimeError: cookies 已过期 (心跳检测失败)
        """
        client = cls()
        client._apply_cookies(cookies)

        # 验证 cookies 是否仍然有效
        if not client._check_login_state():
            raise RuntimeError(
                "Cookies 已过期 (心跳检测失败)，请重新登录。"
                "使用 client.login(phone, password, cookies=cookies) 重新登录。"
            )

        return client

    # ==================== 心跳保活 ====================

    def start_heartbeat(
        self,
        interval: int = 300,
        on_csrf_refresh: Optional[Callable[[str], None]] = None,
    ) -> None:
        """启动后台心跳保活线程

        heartbeatCheck(checkType=1) 请求会返回新的 CSRFToken，
        后台线程会自动更新客户端的 CSRFToken，保持会话活跃。

        Args:
            interval: 心跳间隔秒数，默认 300 (5 分钟)
            on_csrf_refresh: 可选回调，CSRFToken 刷新时调用，参数为新 token

        Example::

            client = HuaweiCloudClient.from_cookies(cookies)
            client.start_heartbeat(interval=300)

            # 随时获取最新的 CSRFToken
            token = client.csrf_token

            # 停止心跳
            client.stop_heartbeat()
        """
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            logger.warning("心跳线程已在运行")
            return

        self._heartbeat_interval = interval
        self._heartbeat_on_refresh = on_csrf_refresh
        self._heartbeat_stop.clear()

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="cloud-space-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()
        logger.info("心跳保活线程已启动 (间隔 %ds)", interval)

    def stop_heartbeat(self) -> None:
        """停止后台心跳保活线程"""
        if self._heartbeat_thread is None or not self._heartbeat_thread.is_alive():
            return

        self._heartbeat_stop.set()
        self._heartbeat_thread.join(timeout=10)
        self._heartbeat_thread = None
        logger.info("心跳保活线程已停止")

    @property
    def heartbeat_running(self) -> bool:
        """心跳线程是否正在运行"""
        return self._heartbeat_thread is not None and self._heartbeat_thread.is_alive()

    @property
    def csrf_token(self) -> str:
        """获取当前最新的 CSRFToken（心跳线程会自动刷新）"""
        return self._csrf_token

    def _heartbeat_loop(self) -> None:
        """后台心跳循环"""
        while not self._heartbeat_stop.wait(timeout=self._heartbeat_interval):
            try:
                self._do_heartbeat()
            except Exception as e:
                logger.warning("心跳请求异常: %s", e)

    def _do_heartbeat(self) -> None:
        """执行一次心跳请求并更新 CSRFToken"""
        trace_id = _generate_traceid("07100")
        url = f"https://cloud.huawei.com/heartbeatCheck?checkType=1&traceId={trace_id}"

        resp = self._session.get(
            url,
            headers=self._module_headers(),
            timeout=30,
            verify=False,
        )

        if resp.status_code != 200:
            logger.warning("心跳请求返回状态码: %s", resp.status_code)
            return

        # 从响应头获取新的 CSRFToken
        new_csrf = resp.headers.get('CSRFToken', '')
        if new_csrf:
            old_csrf = self._csrf_token
            self._csrf_token = new_csrf
            # 更新 session cookie
            self._session.cookies.set('CSRFToken', new_csrf, domain='cloud.huawei.com')
            # 更新 cookies_dict
            self._cookies_dict['CSRFToken'] = new_csrf
            # 更新所有已创建的子模块
            self._update_modules_csrf(new_csrf)

            if old_csrf != new_csrf:
                logger.debug("CSRFToken 已刷新: %s... -> %s...",
                             old_csrf[:12], new_csrf[:12])
                if self._heartbeat_on_refresh:
                    try:
                        self._heartbeat_on_refresh(new_csrf)
                    except Exception as e:
                        logger.warning("on_csrf_refresh 回调异常: %s", e)

        # 从 Set-Cookie 中也同步 CSRFToken
        for cookie in self._session.cookies:
            if cookie.name == 'CSRFToken' and cookie.value and cookie.value != self._csrf_token:
                self._csrf_token = cookie.value
                self._cookies_dict['CSRFToken'] = cookie.value
                self._update_modules_csrf(cookie.value)

        try:
            data = resp.json()
            code = str(data.get("code", "-1"))
            if code != "0":
                logger.warning("心跳返回 code=%s, info=%s", code, data.get("info", ""))
        except Exception:
            pass

        logger.debug("心跳正常")

    def _update_modules_csrf(self, new_csrf: str) -> None:
        """更新所有已创建子模块的 CSRFToken"""
        for mod in (self._notepad, self._contacts, self._gallery,
                    self._drive, self._find_device):
            if mod is not None and hasattr(mod, '_csrf_token'):
                mod._csrf_token = new_csrf

    # ==================== 登出 API ====================

    def logout(self) -> bool:
        """登出华为云空间

        登出流程:
        1. GET /portalLogout — 清除 cloud.huawei.com 域的认证 cookies
        2. GET id1.cloud.huawei.com/CAS/logout — 清除 CAS 域的认证 cookies
        3. POST /html/setCookieValue — 清除 fromActive cookie
        4. GET /v2Logout — 清除 isLogin/needActive 等 cookie

        Returns:
            bool — 登出是否成功
        """
        from .base import _generate_traceid

        # 先停止心跳线程
        self.stop_heartbeat()

        try:
            # Step 1: portalLogout — 清除 cloud.huawei.com 域认证 cookies
            resp = self._session.get(
                "https://cloud.huawei.com/portalLogout",
                allow_redirects=False,
                timeout=30,
                verify=False,
            )
            logger.debug("portalLogout 状态码: %s", resp.status_code)

            # Step 2: CAS logout — 清除 id1 域认证 cookies
            cas_logout_url = (
                "https://id1.cloud.huawei.com/CAS/logout"
                "?service=https%3A%2F%2Fcloud.huawei.com%3A443%2Fv2Logout"
                "&reqClientType=1&loginChannel=1000002"
            )
            resp = self._session.get(
                cas_logout_url,
                allow_redirects=False,
                timeout=30,
                verify=False,
            )
            logger.debug("CAS logout 状态码: %s", resp.status_code)

            # Step 3: setCookieValue — 清除 fromActive
            trace_id = _generate_traceid("25002")
            self._session.post(
                "https://cloud.huawei.com/html/setCookieValue",
                headers={
                    "content-type": "application/json;charset=UTF-8",
                    "origin": "https://cloud.huawei.com",
                    "referer": "https://cloud.huawei.com/",
                },
                json={
                    "cookieName": "fromActive",
                    "value": "",
                    "traceId": trace_id,
                },
                timeout=30,
                verify=False,
            )

            # Step 4: v2Logout — 最终清理
            self._session.get(
                "https://cloud.huawei.com/v2Logout",
                timeout=30,
                verify=False,
            )

            # 清除内部状态
            self._cookies_dict = {}
            self._csrf_token = ''
            self._user_id = ''
            self._device_id = ''
            self._invalidate_modules()

            logger.info("登出成功")
            return True

        except Exception as e:
            logger.error("登出失败: %s", e)
            return False

    # ==================== 凭据访问 ====================

    @property
    def cookies(self) -> Dict[str, str]:
        """当前 cookies 字典"""
        return self._cookies_dict

    # ==================== 子模块 (懒加载) ====================

    @property
    def notepad(self):
        """备忘录模块"""
        if self._notepad is None:
            self._notepad = self._create_module("notepad")
        return self._notepad

    @property
    def contacts(self):
        """联系人模块"""
        if self._contacts is None:
            self._contacts = self._create_module("contacts")
        return self._contacts

    @property
    def gallery(self):
        """图库模块"""
        if self._gallery is None:
            self._gallery = self._create_module("gallery")
        return self._gallery

    @property
    def drive(self):
        """云盘模块"""
        if self._drive is None:
            self._drive = self._create_module("drive")
        return self._drive

    @property
    def find_device(self):
        """查找设备模块"""
        if self._find_device is None:
            self._find_device = self._create_module("find_device")
        return self._find_device

    # ==================== 内部方法 ====================

    def _apply_login_result(self, result: LoginResult) -> None:
        """登录成功后更新内部状态"""
        self._cookies_dict = result.cookies
        self._csrf_token = result.cookies.get('CSRFToken', '')
        self._user_id = result.cookies.get('userId', '')
        self._device_id = result.cookies.get('device_id', '')
        self._invalidate_modules()

    def _apply_cookies(self, cookies: Dict[str, str]) -> None:
        """从 cookies dict 恢复 session"""
        from .auth import (
            _CLOUD_HUAWEI_COM_COOKIE_KEYS,
            _HUAWEI_COM_COOKIE_KEYS,
            _ID1_COOKIE_KEYS,
        )
        for name, value in cookies.items():
            if name.startswith('remember_client_flag'):
                self._session.cookies.set(name, value, domain='.id1.cloud.huawei.com')
            elif name in _ID1_COOKIE_KEYS:
                self._session.cookies.set(name, value, domain='.id1.cloud.huawei.com')
            elif name in _HUAWEI_COM_COOKIE_KEYS:
                self._session.cookies.set(name, value, domain='.huawei.com')
            elif name in _CLOUD_HUAWEI_COM_COOKIE_KEYS:
                self._session.cookies.set(name, value, domain='cloud.huawei.com')
            else:
                self._session.cookies.set(name, value, domain='.huawei.com')
        self._cookies_dict = cookies
        self._csrf_token = cookies.get('CSRFToken', '')
        self._user_id = cookies.get('userId', '')
        self._device_id = cookies.get('device_id', '')
        self._invalidate_modules()

    def _invalidate_modules(self) -> None:
        """登录状态变化后清除子模块缓存，下次访问时重新创建"""
        self._notepad = None
        self._contacts = None
        self._gallery = None
        self._drive = None
        self._find_device = None

    def _check_login_state(self) -> bool:
        """通过 heartbeatCheck(checkType=1) 检查会话是否有效

        心跳请求成功 (code=0) 表示 cookies 有效，
        同时会从响应头更新 CSRFToken。

        Returns:
            True 表示会话有效，False 表示已过期
        """
        try:
            trace_id = _generate_traceid("07100")
            url = f"https://cloud.huawei.com/heartbeatCheck?checkType=1&traceId={trace_id}"
            resp = self._session.get(
                url,
                headers=self._module_headers(),
                timeout=30,
                verify=False,
            )
            if resp.status_code != 200:
                logger.warning("心跳检测返回状态码: %s", resp.status_code)
                return False

            # 从响应头获取新的 CSRFToken
            new_csrf = resp.headers.get('CSRFToken', '')
            if new_csrf:
                self._csrf_token = new_csrf
                self._session.cookies.set('CSRFToken', new_csrf, domain='cloud.huawei.com')
                self._cookies_dict['CSRFToken'] = new_csrf
                self._update_modules_csrf(new_csrf)

            # 从 Set-Cookie 中也同步 CSRFToken
            for cookie in self._session.cookies:
                if cookie.name == 'CSRFToken' and cookie.value and cookie.value != self._csrf_token:
                    self._csrf_token = cookie.value
                    self._cookies_dict['CSRFToken'] = cookie.value
                    self._update_modules_csrf(cookie.value)

            data = resp.json()
            code = str(data.get("code", "-1"))
            if code == "0":
                logger.info("心跳检测: 会话有效")
                return True
            else:
                logger.warning("心跳检测: code=%s, info=%s", code, data.get("info", ""))
                return False

        except Exception as e:
            logger.warning("心跳检测失败: %s", e)
            return False

    def _ensure_device_id(self) -> None:
        """如果 device_id 为空，尝试从 getHomeData 获取"""
        if self._device_id:
            return
        try:
            from .base import _generate_traceid
            trace_id = _generate_traceid("00001")
            resp = self._session.post(
                f"https://cloud.huawei.com/html/getHomeData?traceId={trace_id}",
                headers=self._module_headers(),
                json={"traceId": trace_id},
                timeout=30,
                verify=False,
            )
            if resp.status_code == 200:
                data = resp.json()
                dev_id = data.get("deviceIdForHeader", "")
                if dev_id:
                    self._device_id = str(dev_id)
        except Exception as e:
            logger.debug("获取 device_id 失败: %s", e)

    def _module_headers(self) -> Dict[str, str]:
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

    def _create_module(self, name: str) -> BaseModule:
        """动态创建子模块"""
        self._ensure_device_id()
        module_map = {
            "notepad": ".notepad",
            "contacts": ".contacts",
            "gallery": ".gallery",
            "drive": ".drive",
            "find_device": ".find_device",
        }
        import importlib
        mod = importlib.import_module(module_map[name], package="cloud_space_huawei")
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (isinstance(obj, type)
                    and issubclass(obj, BaseModule)
                    and obj is not BaseModule
                    and not attr_name.startswith('_')):
                return obj(
                    session=self._session,
                    csrf_token=self._csrf_token,
                    user_id=self._user_id,
                    device_id=self._device_id,
                )
        raise RuntimeError(f"模块 {name} 中未找到 BaseModule 子类")
