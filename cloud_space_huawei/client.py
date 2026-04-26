"""核心客户端 — 用户入口，整合登录 + 各子模块"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional

import requests

from .auth import AuthManager, LoginResult
from .base import (
    DEFAULT_TIMEOUT,
    TRACE_COOKIE,
    TRACE_HEARTBEAT,
    TRACE_LOGOUT,
    TRACE_PORTAL,
    TRACE_SPACE,
    BaseModule,
    _generate_traceid,
)

logger = logging.getLogger("cloud-space-huawei")

# 共享状态锁 — 保护 CSRFToken / cookies_dict / user_id 等跨线程共享数据
_state_lock = threading.RLock()


class HuaweiCloudClient:
    """华为云空间 Python SDK 的主入口

    用法 1 — 从账号密码登录::

        client = HuaweiCloudClient()
        result = client.login("手机号", "密码")

        if result.need_verify:
            # 已获取 CSRFToken，session 可用
            # 获取设备列表并触发发送验证码
            send_result = client.send_verify_code(device_index=0)
            code = input("验证码: ")
            client.verify_device(code)

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
        payment: 会员/支付模块
        revisions: 版本管理模块
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
        self._payment: Optional[Any] = None
        self._revisions: Optional[Any] = None

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
            LoginResult — 检查 need_verify 判断是否需要验证码。
            即使 need_verify=True，cookies 中也已包含 CSRFToken，session 可用。
        """
        result = self._auth.login(phone, password, cookies=cookies)
        if result.success:
            self._apply_login_result(result)
        return result

    def send_verify_code(self, device_index: int = 0) -> LoginResult:
        """获取验证设备列表（同时触发服务端发送验证码）

        在 login() 返回 need_verify=True 后调用。
        此方法会获取验证设备列表，服务端在返回设备列表时已自动向默认设备
        发送验证码。

        Args:
            device_index: 选择要验证的设备序号，默认 0（第一个设备）

        Returns:
            LoginResult — 成功时 need_verify=True，auth_devices 包含设备列表
        """
        result = self._auth.send_verify_code(device_index=device_index)
        if result.success:
            self._apply_login_result(result)
        return result

    def verify_device(self, verify_code: str) -> LoginResult:
        """提交设备验证码，完成设备信任认证

        在 send_verify_code() 后调用，提交用户收到的验证码。
        验证成功后会信任当前浏览器，下次登录不再需要验证。

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
          (loginSecLevel=0 表示未信任设备)

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

    @property
    def need_verify(self) -> bool:
        """当前会话是否需要设备信任认证

        通过 loginSecLevel cookie 判断：
        - loginSecLevel=0 表示设备未信任，受限模块（联系人、图库、备忘录、云盘）不可用
        - loginSecLevel>0 表示设备已信任，所有模块可用
        """
        return self._cookies_dict.get('loginSecLevel', '0') == '0'

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
        with _state_lock:
            return self._csrf_token

    def _heartbeat_loop(self) -> None:
        """后台心跳循环"""
        while not self._heartbeat_stop.wait(timeout=self._heartbeat_interval):
            try:
                self._do_heartbeat()
            except (requests.RequestException, OSError) as e:
                logger.warning("心跳请求异常: %s", e)

    def _do_heartbeat(self) -> None:
        """执行一次心跳请求并更新 CSRFToken"""
        trace_id = _generate_traceid(TRACE_HEARTBEAT)
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
            with _state_lock:
                old_csrf = self._csrf_token
                self._csrf_token = new_csrf
                self._session.cookies.set('CSRFToken', new_csrf, domain='cloud.huawei.com')
                self._cookies_dict['CSRFToken'] = new_csrf

            # 更新所有已创建的子模块（在锁外执行避免死锁）
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
            if cookie.name == 'CSRFToken' and cookie.value:
                with _state_lock:
                    if cookie.value != self._csrf_token:
                        self._csrf_token = cookie.value
                        self._cookies_dict['CSRFToken'] = cookie.value
                if cookie.value != new_csrf:
                    self._update_modules_csrf(cookie.value)

        try:
            data = resp.json()
            code = str(data.get("code", "-1"))
            if code != "0":
                logger.warning("心跳返回 code=%s, info=%s", code, data.get("info", ""))
        except ValueError:
            pass

        logger.debug("心跳正常")

    def _update_modules_csrf(self, new_csrf: str) -> None:
        """更新所有已创建子模块的 CSRFToken"""
        for mod in (self._notepad, self._contacts, self._gallery,
                    self._drive, self._find_device,
                    self._payment, self._revisions):
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
            trace_id = _generate_traceid(TRACE_LOGOUT)
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
        """当前 cookies 字典（从 session 动态同步）"""
        # 从 session 中获取最新的 cookie 值
        with _state_lock:
            for name in ("CSRFToken", "shareToken", "JSESSIONID", "userId"):
                value = self._session.cookies.get(name, domain="cloud.huawei.com")
                if value:
                    self._cookies_dict[name] = value
                    if name == "CSRFToken":
                        self._csrf_token = value
            return self._cookies_dict.copy()

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

    @property
    def payment(self):
        """会员/支付模块"""
        if self._payment is None:
            self._payment = self._create_module("payment")
        return self._payment

    @property
    def revisions(self):
        """版本管理模块"""
        if self._revisions is None:
            self._revisions = self._create_module("revisions")
        return self._revisions

    # ==================== 门户级 API ====================

    def get_common_param(self, simplify: bool = True) -> dict:
        """获取通用参数

        Args:
            simplify: 是否精简返回数据，默认 True。精简时仅保留云空间相关
                     配置，去除大量无关的网址和链接。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        resp = self._session.post(
            f"https://cloud.huawei.com/html/getCommonParam?traceId={trace_id}",
            headers=self._module_headers(),
            json={"traceId": trace_id},
            timeout=DEFAULT_TIMEOUT, verify=False,
        )
        data = self._parse_portal_response(resp)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_portal_code(data)
        if simplify:
            data = self._simplify_common_param(data)
        return {"ok": code == "0", "code": code,
                "msg": "通用参数" if code == "0" else f"失败({code})", "data": data}

    @staticmethod
    def _simplify_common_param(data: dict) -> dict:
        """精简通用参数，保留云空间相关内容"""
        return {
            "code": data.get("code", 0),
            "info": data.get("info", ""),
            "lang": data.get("lang", ""),
            "siteCode": data.get("siteCode", ""),
            "siteId": data.get("siteId", ""),
            "portalDomain": data.get("portalDomain", ""),
            "appBrandId": data.get("appBrandId", ""),
            "clientType": data.get("clientType", 0),
            "deviceBrand": data.get("deviceBrand", ""),
            "deviceBrandId": data.get("deviceBrandId", ""),
            "deviceManufacturer": data.get("deviceManufacturer", ""),
            "isGrayWeb": data.get("isGrayWeb", False),
            "isShowPCClientDownloadEntrance": data.get("isShowPCClientDownloadEntrance", ""),
            "cookiesUpdateVersion": data.get("cookiesUpdateVersion", ""),
            "copyDriveFilesMaxNumLimit": data.get("copyDriveFilesMaxNumLimit", 0),
            "driveMultiDomainSwitch": data.get("driveMultiDomainSwitch", False),
            "driveMultiDomainUrlExpiredTimestamp": data.get("driveMultiDomainUrlExpiredTimestamp", 0),
            "cloudPhotoReportEntrySwitch": data.get("cloudPhotoReportEntrySwitch", 0),
            "moreApplicationDataSwitch": data.get("moreApplicationDataSwitch", 0),
            "noticeIntervalTime": data.get("noticeIntervalTime", 0),
            "pointSwitch": data.get("pointSwitch", ""),
            "toolEcologySwitch": data.get("toolEcologySwitch", 0),
            "webPayIAP4Switch": data.get("webPayIAP4Switch", False),
        }

    def get_home_data(self, simplify: bool = True) -> dict:
        """获取首页数据 (含 deviceIdForHeader)

        Args:
            simplify: 是否精简返回数据，默认 True。精简后仅保留用户相关的
                     关键字段，去除大量无用配置项和长链接。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        resp = self._session.post(
            f"https://cloud.huawei.com/html/getHomeData?traceId={trace_id}",
            headers=self._module_headers(),
            json={"traceId": trace_id},
            timeout=DEFAULT_TIMEOUT, verify=False,
        )
        data = self._parse_portal_response(resp)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_portal_code(data)
        dev_id = data.get("deviceIdForHeader", "")
        if dev_id and not self._device_id:
            self._device_id = str(dev_id)
            self._update_modules_csrf(self._csrf_token)
        if simplify:
            data = self._simplify_home_data(data)
        return {"ok": code == "0", "code": code,
                "msg": "首页数据" if code == "0" else f"失败({code})", "data": data}

    @staticmethod
    def _simplify_home_data(data: dict) -> dict:
        """精简首页数据，保留关键字段"""
        return {
            "accountName": data.get("accountName", ""),
            "accountType": data.get("accountType", 0),
            "countryCode": data.get("countryCode", ""),
            "userid": data.get("userid", ""),
            "userEmail": data.get("userEmail", ""),
            "userStatus": data.get("userStatus", ""),
            "userTimeZone": data.get("userTimeZone", ""),
            "gradeCode": data.get("gradeCode", ""),
            "gradeState": data.get("gradeState", 0),
            "hexCode": data.get("hexCode", ""),
            "isLogin": data.get("isLogin", "0"),
            "validToTime": data.get("validToTime", 0),
            "deviceIdForHeader": data.get("deviceIdForHeader", ""),
            "moduleList": data.get("moduleList", []),
            "notifySwitch": data.get("notifySwitch", 0),
            "cloudPhotoSwitch": data.get("cloudPhotoSwitch", 0),
            "huaweiNoteSwitch": data.get("huaweiNoteSwitch", "false"),
            "huaweiNoteOperationSwitch": data.get("huaweiNoteOperationSwitch", 0),
            "newBusinessModelSwitch": data.get("newBusinessModelSwitch", 0),
            "enableNewAppDataManagement": data.get("enableNewAppDataManagement", False),
            "maxUploadSize": data.get("maxUploadSize", 0),
            "maxDownloadSize": data.get("maxDownloadSize", 0),
            "maxUploadSingleFileSize": data.get("maxUploadSingleFileSize", 0),
            "maxUploadNum": data.get("maxUploadNum", 0),
            "maxDownloadNum": data.get("maxDownloadNum", 0),
            "contactMaxSize": data.get("contactMaxSize", 0),
        }

    def get_cookies(self) -> dict:
        """查询服务端 Cookie 值"""
        trace_id = _generate_traceid(TRACE_COOKIE)
        resp = self._session.post(
            f"https://cloud.huawei.com/html/queryCookieValuesByNames?traceId={trace_id}",
            headers=self._module_headers(),
            json={"traceId": trace_id},
            timeout=DEFAULT_TIMEOUT, verify=False,
        )
        data = self._parse_portal_response(resp)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        cookies = data.get("cookies", {})
        code = self._get_portal_code(data)
        return {"ok": code == "0", "code": code,
                "msg": f"获取{len(cookies)}项" if code == "0" else f"失败({code})",
                "data": cookies}

    def heartbeat_check(self) -> dict:
        """心跳检测，保持会话活跃"""
        trace_id = _generate_traceid(TRACE_HEARTBEAT)
        url = f"https://cloud.huawei.com/heartbeatCheck?checkType=1&traceId={trace_id}"
        resp = self._session.get(
            url, headers=self._module_headers(), timeout=DEFAULT_TIMEOUT, verify=False,
        )
        data = self._parse_portal_response(resp)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_portal_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "心跳正常" if code == "0" else f"失败({code})"}

    def notify_poll(self, tag: str = "0", module: str = "portal", timeout: int = 60) -> dict:
        """通知轮询 (长轮询)"""
        trace_id = _generate_traceid(TRACE_HEARTBEAT)
        body = {"tag": tag, "module": module, "traceId": trace_id}
        resp = self._session.post(
            "https://cloud.huawei.com/notify",
            headers=self._module_headers(),
            json=body, timeout=timeout, verify=False,
        )
        data = self._parse_portal_response(resp)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_portal_code(data)
        new_tag = data.get("tag", tag)
        if code == "0":
            return {"ok": True, "code": code, "msg": "有新通知", "data": data, "tag": new_tag}
        elif code == "102":
            return {"ok": True, "code": code, "msg": "长轮询超时(无新通知)", "data": data, "tag": new_tag}
        else:
            return {"ok": False, "code": code, "msg": f"失败(code={code})", "data": data, "tag": new_tag}

    def get_space_info(self, simplify: bool = True) -> dict:
        """获取用户云空间容量等信息

        Args:
            simplify: 是否精简返回数据，默认 True。精简时 deviceList 仅保留
                     deviceAliasName、deviceType、terminalType、frequentlyUsed、
                     loginTime、logoutTime、deviceId 等关键字段。
        """
        trace_id = _generate_traceid(TRACE_SPACE)
        resp = self._session.post(
            f"https://cloud.huawei.com/nsp/getInfos?traceId={trace_id}",
            headers=self._module_headers(),
            json={"traceId": trace_id},
            timeout=DEFAULT_TIMEOUT, verify=False,
        )
        data = self._parse_portal_response(resp)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_portal_code(data)
        ok = code in ("0", "") and "deviceList" in data
        if ok and simplify:
            data = self._simplify_space_info(data)
        return {"ok": ok, "code": code or "0",
                "msg": "空间信息" if ok else f"失败({code})", "data": data}

    @staticmethod
    def _simplify_space_info(data: dict) -> dict:
        """精简空间信息，保留关键字段"""
        result = {
            "accountSensit": data.get("accountSensit", ""),
            "userName": data.get("userName", ""),
            "userImg": data.get("userImg", ""),
        }

        def _simplify_device(device: dict) -> dict:
            return {
                "deviceAliasName": device.get("deviceAliasName", ""),
                "deviceType": device.get("deviceType", 0),
                "terminalType": device.get("terminalType", ""),
                "frequentlyUsed": device.get("frequentlyUsed", 0),
                "loginTime": device.get("loginTime", ""),
                "logoutTime": device.get("logoutTime", ""),
                "deviceId": device.get("deviceId", ""),
            }

        result["deviceList"] = [_simplify_device(d) for d in data.get("deviceList", [])]
        return result

    def refresh_cookies(self) -> dict:
        """刷新 cookies 并更新客户端状态"""
        trace_id = _generate_traceid(TRACE_COOKIE)
        resp = self._session.post(
            f"https://cloud.huawei.com/html/queryCookieValuesByNames?traceId={trace_id}",
            headers=self._module_headers(),
            json={"traceId": trace_id},
            timeout=DEFAULT_TIMEOUT, verify=False,
        )
        data = self._parse_portal_response(resp)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        cookies = data.get("cookies", {})
        code = self._get_portal_code(data)
        if code == "0" and cookies:
            self._csrf_token = cookies.get("CSRFToken", self._csrf_token)
            self._user_id = cookies.get("userId", self._user_id)
            self._update_modules_csrf(self._csrf_token)
        return {"ok": code == "0", "code": code,
                "msg": f"刷新{len(cookies)}项" if code == "0" else f"失败({code})"}

    # ==================== 补充 API ====================

    def _supp_headers(self, trace_id: str = "") -> Dict[str, str]:
        """补充 API 专用请求头

        基于 _module_headers()，额外添加 x-hw-trace-id。
        """
        h = self._module_headers()
        if trace_id:
            h["x-hw-trace-id"] = trace_id
        return h

    @staticmethod
    def _parse_supp_response(resp: requests.Response) -> dict:
        """解析补充 API 响应 — 兼容多种响应格式

        补充 API 的响应格式不统一:
        - 标准: ``{"code": "0", ...}``
        - 无 code: ``{"deCardOps": [...], ...}``
        - HTML: ``<!DOCTYPE html>...``
        """
        try:
            if resp.status_code == 200:
                # 先尝试 JSON 解析
                try:
                    data = resp.json()
                except (ValueError, TypeError):
                    # 非 JSON 响应 (如 HTML 页面)
                    return {"error": "非JSON响应", "_code": "-3",
                            "raw_text": resp.text[:200]}

                # 检查 402
                code = str(data.get("code", ""))
                if code == "402":
                    return {"error": "设备未认证(402)", "_code": "402"}
                return data
            if resp.status_code == 400:
                return {"error": "HTTP 400", "_code": "400"}
            if resp.status_code == 401:
                return {"error": "认证失败(401)", "_code": "401"}
            if resp.status_code == 402:
                return {"error": "设备未认证(402)", "_code": "402"}
            return {"error": f"HTTP {resp.status_code}", "_code": str(resp.status_code)}
        except requests.RequestException as e:
            return {"error": "请求异常", "detail": str(e), "_code": "-1"}

    @staticmethod
    def _get_supp_code(data: dict) -> str:
        """从补充 API 响应中提取 code — 兼容多种格式"""
        if "code" in data:
            return str(data["code"])
        # 无 code 字段的响应视为成功 (200 状态 + 有数据)
        if "error" not in data:
            return "0"
        return ""

    def get_user_space(self) -> dict:
        """获取用户空间详情

        返回详细的云空间使用情况，包括已用空间、总空间等。
        若端点不可用 (返回 400)，回退到 get_space_info()。
        """
        trace_id = _generate_traceid(TRACE_SPACE)
        try:
            resp = self._session.post(
                f"https://cloud.huawei.com/nsp/getUserSpace?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                json={"traceId": trace_id},
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data and data.get("_code") == "400":
                # 端点可能不支持，回退到 get_space_info
                logger.debug("getUserSpace 返回 400，回退到 get_space_info")
                fallback = self.get_space_info()
                fallback["msg"] = "用户空间详情(回退)"
                return fallback
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            code = self._get_supp_code(data)
            return {"ok": code == "0", "code": code,
                    "msg": "用户空间详情" if code == "0" else f"失败({code})",
                    "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def get_family_share_info(self) -> dict:
        """获取家庭共享信息

        返回家庭空间共享成员和共享空间信息。
        """
        trace_id = _generate_traceid(TRACE_SPACE)
        try:
            resp = self._session.post(
                f"https://cloud.huawei.com/nsp/getFamilyShareInfo?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                json={"traceId": trace_id},
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            code = self._get_supp_code(data)
            return {"ok": code == "0", "code": code,
                    "msg": "家庭共享信息" if code == "0" else f"失败({code})",
                    "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def get_device_and_wallet(self) -> dict:
        """获取设备和钱包信息

        返回用户的设备信息和钱包（余额等）信息。
        注意: 该接口响应无 code 字段，200 即视为成功。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        try:
            resp = self._session.post(
                f"https://cloud.huawei.com/setting/getDeviceAndWallet?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                json={"traceId": trace_id},
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            # 该接口响应无 code 字段，200 即成功
            return {"ok": True, "code": "0",
                    "msg": "设备和钱包信息", "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def get_personal_info(self) -> dict:
        """获取个人信息

        返回用户的个人信息。此接口返回 HTML 页面而非 JSON，
        将从页面中解析关键数据。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        try:
            resp = self._session.get(
                f"https://cloud.huawei.com/personalInfo?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            if resp.status_code != 200:
                return {"ok": False, "code": str(resp.status_code),
                        "msg": f"HTTP {resp.status_code}"}
            # personalInfo 返回 HTML，尝试提取嵌入的 JSON 数据
            text = resp.text
            info = {}
            # 尝试从 HTML 中提取 accountName
            import re
            m = re.search(r'"accountName"\s*:\s*"([^"]*)"', text)
            if m:
                info["accountName"] = m.group(1)
            m = re.search(r'"userEmail"\s*:\s*"([^"]*)"', text)
            if m:
                info["userEmail"] = m.group(1)
            m = re.search(r'"countryCode"\s*:\s*"([^"]*)"', text)
            if m:
                info["countryCode"] = m.group(1)
            # 如果从 get_home_data 能获取更完整的信息，优先使用
            home = self.get_home_data(simplify=True)
            if home.get("ok"):
                home_data = home.get("data", {})
                info.setdefault("accountName", home_data.get("accountName", ""))
                info.setdefault("userEmail", home_data.get("userEmail", ""))
                info.setdefault("countryCode", home_data.get("countryCode", ""))
                info["userid"] = home_data.get("userid", "")
                info["gradeCode"] = home_data.get("gradeCode", "")
            if info:
                return {"ok": True, "code": "0", "msg": "个人信息", "data": info}
            return {"ok": False, "code": "-3", "msg": "无法解析个人信息"}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def get_language_map(self) -> dict:
        """获取语言映射

        返回多语言配置映射。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        try:
            resp = self._session.post(
                f"https://cloud.huawei.com/language/getLanguageMap?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                json={"traceId": trace_id},
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            code = self._get_supp_code(data)
            return {"ok": code == "0", "code": code,
                    "msg": "语言映射" if code == "0" else f"失败({code})",
                    "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def get_client_log_report(self) -> dict:
        """获取客户端日志报告配置

        返回客户端日志上报的相关配置信息。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        try:
            resp = self._session.post(
                f"https://cloud.huawei.com/basic/getClientLogReport?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                json={"traceId": trace_id},
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            code = self._get_supp_code(data)
            return {"ok": code == "0", "code": code,
                    "msg": "客户端日志配置" if code == "0" else f"失败({code})",
                    "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def update_client_log_report(self, log_data: dict = None) -> dict:
        """更新客户端日志报告

        上报客户端日志信息。

        Args:
            log_data: 日志数据
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        body = {"traceId": trace_id}
        if log_data:
            body.update(log_data)
        try:
            resp = self._session.post(
                f"https://cloud.huawei.com/basic/updateClientLogReport?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                json=body,
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            code = self._get_supp_code(data)
            return {"ok": code == "0", "code": code,
                    "msg": "日志上报成功" if code == "0" else f"失败({code})",
                    "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def data_extract_query_task(self) -> dict:
        """查询数据提取任务

        返回数据提取任务的状态和进度。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        try:
            resp = self._session.get(
                f"https://cloud.huawei.com/dataExtract/queryTask?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            code = self._get_supp_code(data)
            return {"ok": code == "0", "code": code,
                    "msg": "数据提取任务" if code == "0" else f"失败({code})",
                    "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def get_app_info_list_by_consent(self) -> dict:
        """获取应用数据管理信息

        返回用户授权的应用数据管理列表。
        注意: 该接口可能返回 code=-3 (参数无效)，表示服务端
        需要特定参数但当前账户无数据。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        try:
            resp = self._session.post(
                f"https://cloud.huawei.com/appdatamanagement/getAppInfoListByConsent?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                json={"traceId": trace_id},
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            code = self._get_supp_code(data)
            # code=-3 表示参数无效 (服务端可能需要特定参数)
            return {"ok": code == "0", "code": code,
                    "msg": "应用数据管理" if code == "0" else
                           (f"无数据({code})" if code == "-3" else f"失败({code})"),
                    "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def get_space_banner_config(self) -> dict:
        """获取云空间横幅配置

        返回云空间首页横幅的配置信息。
        注意: 该接口可能返回 code=-1 (获取失败)，表示当前
        无可用横幅配置。
        """
        trace_id = _generate_traceid(TRACE_PORTAL)
        try:
            resp = self._session.post(
                f"https://cloud.huawei.com/om/getHiCloudSpaceBannerConfig?traceId={trace_id}",
                headers=self._supp_headers(trace_id),
                json={"traceId": trace_id},
                timeout=DEFAULT_TIMEOUT, verify=False,
            )
            data = self._parse_supp_response(resp)
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            code = self._get_supp_code(data)
            return {"ok": code == "0", "code": code,
                    "msg": "横幅配置" if code == "0" else
                           (f"无配置({code})" if code == "-1" else f"失败({code})"),
                    "data": data}
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    # ==================== 内部方法 ====================

    def _apply_login_result(self, result: LoginResult) -> None:
        """登录成功后更新内部状态

        现在登录完成后 cookies 已包含完整的 cloud.huawei.com 域数据，
        包括 CSRFToken、userId、isLogin、loginSecLevel、functionSupport、
        webOfficeEditToken、shareToken 等。
        """
        with _state_lock:
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
        with _state_lock:
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
        self._payment = None
        self._revisions = None

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
                with _state_lock:
                    self._csrf_token = new_csrf
                    self._session.cookies.set('CSRFToken', new_csrf, domain='cloud.huawei.com')
                    self._cookies_dict['CSRFToken'] = new_csrf
                self._update_modules_csrf(new_csrf)

            # 从 Set-Cookie 中也同步 CSRFToken
            for cookie in self._session.cookies:
                if cookie.name == 'CSRFToken' and cookie.value:
                    with _state_lock:
                        if cookie.value != self._csrf_token:
                            self._csrf_token = cookie.value
                            self._cookies_dict['CSRFToken'] = cookie.value
                    if cookie.value != new_csrf:
                        self._update_modules_csrf(cookie.value)

            data = resp.json()
            code = str(data.get("code", "-1"))
            if code == "0":
                logger.info("心跳检测: 会话有效")
                return True
            else:
                logger.warning("心跳检测: code=%s, info=%s", code, data.get("info", ""))
                return False

        except (requests.RequestException, OSError) as e:
            logger.warning("心跳检测失败: %s", e)
            return False

    def _ensure_device_id(self) -> None:
        """如果 device_id 为空，尝试从 get_home_data 获取"""
        if self._device_id:
            return
        try:
            result = self.get_home_data()
            if result.get("ok"):
                dev_id = result.get("data", {}).get("deviceIdForHeader", "")
                if dev_id:
                    self._device_id = str(dev_id)
        except (requests.RequestException, OSError) as e:
            logger.debug("获取 device_id 失败: %s", e)

    @staticmethod
    def _get_portal_code(data: dict) -> str:
        """从门户级响应中提取 code"""
        if "code" in data:
            return str(data["code"])
        if "Result" in data and isinstance(data["Result"], dict):
            return str(data["Result"].get("code", ""))
        # 部分接口使用 result.resultCode 格式
        if "result" in data and isinstance(data["result"], dict):
            rc = data["result"].get("resultCode", "")
            if rc:
                return str(rc)
        return ""

    @staticmethod
    def _parse_portal_response(resp: requests.Response) -> dict:
        """解析门户级 API 响应，统一处理错误"""
        try:
            if resp.status_code == 200:
                data = resp.json()
                code = str(data.get("code", ""))
                if code == "402":
                    return {"error": "设备未认证(402)，请先完成设备信任认证", "_code": "402"}
                result_code = str(data.get("Result", {}).get("code", ""))
                if result_code == "402":
                    return {"error": "设备未认证(402)，请先完成设备信任认证", "_code": "402"}
                return data
            if resp.status_code == 401:
                return {"error": "认证失败(401)，cookies 已过期", "_code": "401"}
            if resp.status_code == 402:
                return {"error": "设备未认证(402)，请先完成设备信任认证", "_code": "402"}
            return {"error": f"HTTP {resp.status_code}", "_code": str(resp.status_code)}
        except requests.RequestException as e:
            return {"error": "请求异常", "detail": str(e), "_code": "-1"}
        except (ValueError, TypeError) as e:
            return {"error": "响应解析失败", "detail": str(e), "_code": "-2"}

    def _module_headers(self) -> Dict[str, str]:
        # 实时从 session.cookies 获取最新 CSRFToken，避免使用缓存过期 token
        csrf = self._session.cookies.get("CSRFToken", domain="cloud.huawei.com") or self._csrf_token
        return {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "csrftoken": csrf,
            "userid": self._user_id,
            "x-hw-account-brand-id": "0",
            "x-hw-app-brand-id": "1",
            "x-hw-client-mode": "frontend",
            "x-hw-device-brand": "HUAWEI",
            "x-hw-device-category": "Web",
            "x-hw-device-id": self._device_id,
            "x-hw-device-manufacturer": "HUAWEI",
            "x-hw-device-type": "7",
            "x-hw-framework-type": "0",
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
            "payment": ".payment",
            "revisions": ".revisions",
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
