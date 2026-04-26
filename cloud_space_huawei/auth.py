"""华为云空间登录模块

两种登录场景:
1. 信任设备: login(cookies=...) → need_verify=False, 直接获得完整 cookies
2. 新设备:   login() → need_verify=True, cookies 中已包含 CSRFToken

新设备登录时，login() 会先完成 OAuth 流程获取 CSRFToken，然后返回 need_verify=True。
此时用户已有有效的 session（可以调用需要 CSRFToken 的 API），但设备尚未受信任。
注意：login() 不会自动获取验证设备列表，避免触发服务端发送验证码。
用户可通过 send_verify_code() 获取设备列表（此时服务端会自动向默认设备发送验证码），
再通过 verify_device() 提交验证码完成信任认证。

登录完成后，用户应保存 cookies，下次直接使用 cookies 登录即可跳过设备验证。

完整 cookies 获取流程:
- homeTransit (302) → Set-Cookie: needActive, userId
- GET /home (200) → Set-Cookie: isLogin=1, CSRFToken (首次颁发)
- POST /html/getHomeData → 轮换 CSRFToken, 设置 loginSecLevel/functionSupport/webOfficeEditToken/shareToken
- POST /html/queryCookieValuesByNames → 获取服务端已知 cookie 值
- GET /heartbeatCheck → 再次轮换 CSRFToken (保持新鲜)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import random
import string
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
import urllib3

from .fingerprint import (
    get_fingerprint as _get_real_fingerprint,
    clear_cache as _clear_fingerprint_cache,
    save_fingerprint as _save_fingerprint,
)

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ===================== 工具函数 =====================

def _sha1_hex(data: str) -> str:
    return hashlib.sha1(data.encode('utf-8')).hexdigest()


# 设备指纹在同一次登录会话中保持一致（服务端可能验证指纹一致性）
_fp_cache: Optional[str] = None


def _generate_fp() -> str:
    """生成设备指纹 (使用 Playwright 获取真实浏览器指纹)

    通过 Playwright 启动 headless Chrome 获取真实的 canvas/webgl 指纹，
    确保与华为服务器验证逻辑一致。
    指纹值在同一次进程内缓存，保证同一会话内所有请求使用相同指纹。
    """
    global _fp_cache
    if _fp_cache is not None:
        return _fp_cache

    # 使用 Playwright 获取真实指纹（会启动 headless Chrome）
    logger.info("[指纹] 正在通过 Playwright 获取真实浏览器指纹...")
    _fp_cache = _get_real_fingerprint()
    logger.info(f"[指纹] 指纹获取成功: {_fp_cache[:30]}...")
    return _fp_cache


# ===================== 数据类 =====================

@dataclass
class LoginResult:
    """登录结果

    用法::

        result = auth.login(phone, pwd)
        if not result:
            print(result.error)
        elif result.need_verify:
            # 已获取 CSRFToken，session 可用，但设备未信任
            # 获取设备列表（同时触发发送验证码）
            send_result = auth.send_verify_code(device_index=0)
            code = input("验证码: ")
            auth.verify_device(code)
        # 保存 cookies 即可，cookies 中已包含 CSRFToken
        save_json("cookies.json", result.cookies)
    """
    success: bool
    need_verify: bool = False
    cookies: Dict[str, str] = field(default_factory=dict)
    auth_devices: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""
    detail: Any = None

    def __bool__(self) -> bool:
        return self.success


# ===================== 常量 =====================

_CLIENT_ID = '4805300'
_REQ_CLIENT_TYPE = '1'
_LOGIN_CHANNEL = '1000002'
_LANG = 'zh-cn'
_SERVICE = 'https://cloud.huawei.com:443/others/login.action'
_SCOPE = 'https://www.huawei.com/auth/account/pwdlowlogin'

_ID1_COOKIE_KEYS = {
    'JSESSIONID', 'CASTGC', 'CAS_THEME_NAME', 'VERSION_NO',
    'hwid_cas_sid', 'sid', 'cplang', 'cookieBannerOnOff',
    'HW_id_id1_cloud_huawei_com_id1_cloud_huawei_com',
    'HW_idts_id1_cloud_huawei_com_id1_cloud_huawei_com',
    'HW_refts_id1_cloud_huawei_com_id1_cloud_huawei_com',
    'HW_idn_id1_cloud_huawei_com_id1_cloud_huawei_com',
    'HW_idvc_id1_cloud_huawei_com_id1_cloud_huawei_com',
    'HW_viewts_id1_cloud_huawei_com_id1_cloud_huawei_com',
}
_HUAWEI_COM_COOKIE_KEYS = {
    'CASLOGINSITE', 'LOGINACCSITE', 'HuaweiID_CAS_ISCASLOGIN',
    'siteID', 'loginID', 'token',
}
_CLOUD_HUAWEI_COM_COOKIE_KEYS = {
    'isLogin', 'CSRFToken', 'userId', 'needActive', 'loginSecLevel',
    'functionSupport', 'webOfficeEditToken', 'shareToken',
    'HWWAFSESID', 'HWWAFSESTIME',
    'HW_id_hicloudportal_2_cloud_huawei_com',
    'HW_idts_hicloudportal_2_cloud_huawei_com',
    'HW_refts_hicloudportal_2_cloud_huawei_com',
    'HW_idn_hicloudportal_2_cloud_huawei_com',
    'HW_idvc_hicloudportal_2_cloud_huawei_com',
    'HW_viewts_hicloudportal_2_cloud_huawei_com',
}
# 登录时需要从旧 cookies 中清除的 id1 域 cookies（这些在重新登录时会被服务端重新签发）
_ID1_SESSION_COOKIE_KEYS = {
    'JSESSIONID', 'CASTGC', 'CAS_THEME_NAME', 'VERSION_NO',
}
# 登录时需要从旧 cookies 中清除的 cloud.huawei.com 域 cookies
# 这些是会话级的认证 cookies，过期后无效，重新登录时会被服务端重新签发
_CLOUD_SESSION_COOKIE_KEYS = {
    'isLogin', 'CSRFToken', 'userId', 'needActive', 'loginSecLevel',
    'functionSupport', 'webOfficeEditToken', 'shareToken',
    'HWWAFSESID', 'HWWAFSESTIME',
    'loginID', 'token', 'siteID',
}


# ===================== 登录器 =====================

class AuthManager:
    """管理华为云空间的登录流程"""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0'
            ),
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        self.session.verify = False
        # 登录流程内部状态
        self._phone: str = ''
        self._password: str = ''
        self._page_token: Optional[str] = None
        self._page_token_key: Optional[str] = None
        self._flow_id: Optional[str] = None
        self._auth_page_token: Optional[str] = None
        self._auth_page_token_key: Optional[str] = None
        self._auth_devices: List[Dict[str, Any]] = []
        self._ext_info: str = ''
        self._random_code_id: str = ''
        self._session_code_key: str = ''
        self._saved_hwid: str = ''

    # ==================== 公开 API ====================

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
        self._phone = phone
        self._password = password

        # Step 1: 初始化 session — 先访问主页建立 cookie 上下文
        self.session.get('https://cloud.huawei.com/', allow_redirects=True)

        # 在 session 初始化后再应用旧的 cookies，避免初始化过程中
        # 服务端清除过期 cookies 导致我们保存的关键 cookie 也被清除
        if cookies:
            self._apply_login_cookies(cookies)
            self._saved_hwid = cookies.get('hwid_cas_sid', '') or cookies.get('sid', '')

        # Step 2: 获取页面信息
        login_url = self._build_login_url()
        self.session.get(login_url)

        self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/common/getBaseSwitchInfo',
            {'themeName': 'huawei', 'lang': _LANG, 'supportHarmonyTheme': 'false'},
        )

        timestamp = str(int(time.time() * 1000))
        url_param = self._build_url_param(timestamp)
        resp = self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/login/getPageInfo',
            {
                'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
                'clientID': _CLIENT_ID, 'lang': _LANG, 'languageCode': _LANG,
                'loginUrl': _SERVICE, 'service': _SERVICE,
                'scenesType': '0', 'scope': _SCOPE, 'time': timestamp,
                'pageName': 'login', 'interfaceName': 'login/getPageInfo',
                'supportHarmonyTheme': 'false', 'urlParam': url_param, 'regionCode': 'cn',
            },
            referer=login_url,
        )
        result = resp.json()
        if result.get('isSuccess') != 1:
            return LoginResult(False, error='getPageInfo失败', detail=result)

        self._page_token = result['pageToken']
        self._page_token_key = result['pageTokenKey']
        self._flow_id = result['localInfo']['flowID']

        # Step 3: 设备指纹 + 健康检测
        self._step_dev()
        self._step_health()

        # Step 4: 风险检测
        risk_result = self._step_risk()
        if risk_result is not None:
            return risk_result

        # Step 5: 密码登录
        return self._step_password_login()

    def send_verify_code(self, device_index: int = 0) -> LoginResult:
        """获取验证设备列表（同时触发服务端发送验证码）

        在 login() 返回 need_verify=True 后调用。
        此方法会获取验证设备列表，服务端在返回设备列表时已自动向默认设备
        发送验证码（getPageInfo 返回的 authCodeSentList 即为已发送验证码的设备列表）。

        Args:
            device_index: 选择要验证的设备序号，默认 0（第一个设备），
                          仅用于标记哪个设备已发送验证码，不影响验证码发送。

        Returns:
            LoginResult — 成功时 need_verify=True，auth_devices 包含设备列表
        """
        # 首次调用时获取设备列表（getPageInfo 会触发服务端发送验证码）
        if not self._auth_devices:
            devices_result = self._step_get_auth_devices()
            if not devices_result:
                return devices_result

        if not self._auth_devices:
            return LoginResult(False, error='没有可用的验证设备')

        if device_index < 0 or device_index >= len(self._auth_devices):
            return LoginResult(False, error=f'设备序号 {device_index} 超出范围（共 {len(self._auth_devices)} 个设备）')

        # 标记指定设备为已发送验证码
        device = self._auth_devices[device_index]
        device['sent'] = 1

        return LoginResult(
            success=True,
            need_verify=True,
            cookies=self._get_cookies_dict(),
            auth_devices=self._auth_devices,
        )

    def verify_device(self, verify_code: str) -> LoginResult:
        """提交设备验证码，完成设备信任认证

        在 send_verify_code() 后调用，提交用户收到的验证码。
        验证成功后会信任当前浏览器，并用新的 callbackURL 重新走 OAuth 流程，
        获取认证后的完整 cookies（含更新后的 loginSecLevel）。

        Args:
            verify_code: 设备上收到的验证码

        Returns:
            LoginResult — 成功后 cookies 已更新（含信任设备信息和认证后的 loginSecLevel）
        """
        device = None
        for d in self._auth_devices:
            if d.get('sent') == 1:
                device = d
                break
        if device is None and self._auth_devices:
            device = self._auth_devices[0]
        if device is None:
            return LoginResult(False, error='没有可用的验证设备，请先调用 send_verify_code()')

        verify_account_name = str(device.get('name', ''))
        verify_account_type = device.get('accountType', -1)

        resp = self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/cloudAuthLogin',
            {
                'pageToken': self._auth_page_token, 'pageTokenKey': self._auth_page_token_key,
                'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
                'lang': _LANG, 'languageCode': _LANG,
                'twoStepVerifyCode': verify_code,
                'verifyAccountType': str(verify_account_type),
                'verifyUserAccount': verify_account_name,
            },
        )
        auth_result = resp.json()
        if auth_result.get('isSuccess') != 1:
            return LoginResult(False, error='验证码错误', detail=auth_result)

        # 信任浏览器
        self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/updateTrustBrowser',
            {
                'pageToken': self._auth_page_token, 'pageTokenKey': self._auth_page_token_key,
                'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
                'lang': _LANG, 'languageCode': _LANG,
                'operType': '2', 'trustBrowser': '1',
            },
        )

        # 用验证后返回的 callbackURL 重新走 OAuth 流程，获取认证后的完整 cookies
        # 必须清除第一次 OAuth 流程（_step_password_login 中）设置的干扰 cookies，
        # 否则旧的 loginID/token/JSESSIONID 会导致第二次 OAuth login 失败
        self._clear_oauth_session_cookies()

        callback_url = auth_result.get('callbackURL', '')
        if callback_url:
            result = self._finish_oauth(callback_url)
            # 登录成功（设备已认证），保存指纹
            if result.success and not result.need_verify:
                _save_fingerprint(_fp_cache)
            return result

        # 如果没有 callbackURL，回退到直接返回当前 cookies
        cookies = self._get_cookies_dict()
        return LoginResult(
            success=True,
            need_verify=False,
            cookies=cookies,
        )

    def restore_session(self, cookies: Dict[str, str]) -> bool:
        """从 cookies 恢复 session，返回是否仍有效"""
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain='.huawei.com')
        try:
            resp = self.session.get('https://cloud.huawei.com/home', allow_redirects=False)
            if resp.status_code == 200:
                return True
            if resp.status_code == 302:
                loc = resp.headers.get('Location', '')
                return not ('login' in loc.lower() or 'id1.cloud.huawei.com' in loc)
            return False
        except Exception:
            return False

    # ==================== 内部步骤 ====================

    def _build_login_url(self) -> str:
        return (
            f"https://id1.cloud.huawei.com/CAS/portal/cloudIframeLogin.html"
            f"?loginUrl={urllib.parse.quote(_SERVICE, safe='')}"
            f"&service={urllib.parse.quote(_SERVICE, safe='')}"
            f"&reqClientType={_REQ_CLIENT_TYPE}"
            f"&loginChannel={_LOGIN_CHANNEL}"
            f"&lang={_LANG}&countryCode=cn&scenesType=0"
            f"&clientID={_CLIENT_ID}"
            f"&scope={urllib.parse.quote(_SCOPE, safe='')}"
            f"&time={int(time.time() * 1000)}"
        )

    def _build_url_param(self, timestamp: str) -> str:
        return (
            f'loginUrl={urllib.parse.quote(_SERVICE, safe="")}'
            f'&service={urllib.parse.quote(_SERVICE, safe="")}'
            f'&reqClientType={_REQ_CLIENT_TYPE}'
            f'&loginChannel={_LOGIN_CHANNEL}'
            f'&lang={_LANG}'
            f'&countryCode=cn&scenesType=0'
            f'&clientID={_CLIENT_ID}'
            f'&scope={urllib.parse.quote(_SCOPE, safe="")}'
            f'&time={timestamp}'
        )

    @staticmethod
    def _reflush() -> str:
        return str(random.random())

    @staticmethod
    def _cversion() -> str:
        return 'UP_CAS_6.26.1.100_blue'

    def _post_form(
        self,
        url: str,
        data: Dict[str, Any],
        origin: str = 'https://id1.cloud.huawei.com',
        referer: str = '',
    ) -> requests.Response:
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Origin': origin}
        if referer:
            headers['Referer'] = referer
        sep = '&' if '?' in url else '?'
        full_url = f'{url}{sep}reflushCode={self._reflush()}&cVersion={self._cversion()}'
        return self.session.post(full_url, data=data, headers=headers)

    def _step_dev(self) -> None:
        fp_value = _generate_fp()
        dev_data: Dict[str, Any] = {
            'pageToken': self._page_token, 'pageTokenKey': self._page_token_key,
            'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
            'clientID': _CLIENT_ID, 'lang': _LANG, 'languageCode': _LANG,
            'fp': fp_value,
        }
        if self._saved_hwid:
            dev_data['hwid_cas_sid'] = self._saved_hwid
        resp = self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/dev', dev_data,
        )
        try:
            dev_result = resp.json()
            dev_sid = dev_result.get('sid', '')
            if dev_sid:
                self._saved_hwid = dev_sid
        except Exception:
            pass
        if not self._saved_hwid:
            for cookie in self.session.cookies:
                if cookie.name == 'hwid_cas_sid' and cookie.value:
                    self._saved_hwid = cookie.value
                    break

    def _step_health(self) -> None:
        self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/analysisHealth',
            {
                'pageToken': self._page_token, 'pageTokenKey': self._page_token_key,
                'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
                'clientID': _CLIENT_ID, 'lang': _LANG, 'languageCode': _LANG,
                'operType': '1000',
                'message': json.dumps({
                    "currentUri": "/CAS/portal/cloudIframeLogin.html",
                    "isOpenCookie": "true", "isOpenPerformance": True,
                    "isSupportES6": True, "dNSTake": "0", "tCPTake": "0",
                    "reqRespTake": "32", "totalTake": "557", "whiteScreenTake": "36",
                    "resourceDataSize": 1212952, "domDisplayTake": "404",
                    "reqReadyTake": "4",
                    "currentLocaleTime": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "resources": [], "extInfo": {"isSwitchWiseContent2SLB": False}
                }),
                'illnessType': '0', 'isIframe': 'true', 'service': _SERVICE,
            },
        )

    def _get_image_verify_code(self) -> Optional[str]:
        """获取图片验证码

        从服务器获取图片验证码，返回验证码ID（用于提交）和图片数据（用于显示）。

        Returns:
            tuple: (verify_id, image_data) 或 None
        """
        try:
            # 先请求获取验证码ID和图片
            resp = self.session.get(
                f'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/getVerifyImage'
                f'?pageToken={self._page_token}&pageTokenKey={self._page_token_key}'
                f'&reqClientType={_REQ_CLIENT_TYPE}&loginChannel={_LOGIN_CHANNEL}'
                f'&clientID={_CLIENT_ID}&lang={_LANG}&v=1',
                headers={'Referer': 'https://id1.cloud.huawei.com/CAS/portal/cloudIframeLogin.html'},
                timeout=30,
            )
            if resp.status_code != 200:
                return None

            result = resp.json()
            verify_id = result.get('verifyId', '')
            image_base64 = result.get('img', '')

            if not verify_id or not image_base64:
                return None

            return verify_id, image_base64
        except Exception as e:
            logger.warning("获取图片验证码失败: %s", e)
            return None

    def _step_risk(self) -> Optional[LoginResult]:
        resp = self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/chkRisk',
            {
                'pageToken': self._page_token, 'pageTokenKey': self._page_token_key,
                'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
                'clientID': _CLIENT_ID, 'lang': _LANG, 'languageCode': _LANG,
                'userAccount': self._phone, 'operType': '0', 'lowLogin': '',
                'service': _SERVICE, 'scope': _SCOPE,
            },
        )
        risk_result = resp.json()
        if risk_result.get('isSuccess') != 1:
            return LoginResult(False, error='chkRisk失败', detail=risk_result)
        self._ext_info = risk_result.get('extInfo', '')
        return None

    def _step_password_login(self) -> LoginResult:
        """Step 5: 提交密码登录"""
        login_data = {
            'pageToken': self._page_token, 'pageTokenKey': self._page_token_key,
            'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
            'clientID': _CLIENT_ID, 'lang': _LANG, 'languageCode': _LANG,
            'loginUrl': _SERVICE, 'service': _SERVICE,
            'quickAuth': 'false', 'isThirdBind': '0', 'hwmeta': '',
            'lowLogin': 'true', 'userAccount': self._phone,
            'password': self._password, 'scope': _SCOPE,
            'extInfo': self._ext_info,
        }

        resp = self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/remoteLogin', login_data,
        )
        login_result = resp.json()

        # 图片验证码错误重试 (errorCode == '10000201')
        retry_count = 0
        while login_result.get('errorCode') == '10000201' and retry_count < 3:
            retry_count += 1
            logger.info("图片验证码错误，第 %d 次重试", retry_count)

            # 获取新的图片验证码
            verify_info = self._get_image_verify_code()
            if not verify_info:
                logger.warning("获取图片验证码失败，跳过重试")
                break

            verify_id, image_base64 = verify_info

            # 保存图片验证码到临时文件供用户查看
            try:
                import base64
                image_data = base64.b64decode(image_base64)
                image_path = os.path.join(os.path.expanduser("~"), "huawei_verify_code.png")
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                logger.info("图片验证码已保存到: %s", image_path)
                print(f"\n需要输入图片验证码")
                print(f"验证码图片已保存到: {image_path}")
                print(f"请打开图片查看验证码，输入后回车继续（或输入 'q' 退出）:")
            except Exception as e:
                logger.warning("保存验证码图片失败: %s", e)
                print(f"\n需要输入图片验证码（base64长度: {len(image_base64)}）:")

            # 提示用户输入验证码
            user_input = input("请输入图片验证码: ").strip()
            if user_input.lower() == 'q':
                return LoginResult(False, error='用户取消')

            # 重试登录，携带新的验证码
            login_data['verifyCode'] = user_input
            login_data['verifyId'] = verify_id
            resp = self._post_form(
                'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/remoteLogin', login_data,
            )
            login_result = resp.json()

        if login_result.get('isSuccess') != 1:
            return LoginResult(False, error='密码登录失败', detail=login_result)

        need_verify = bool(login_result.get('needPopTrust', False))
        callback_url = login_result.get('callbackURL', '')

        # 无论是否需要设备验证，都先完成 OAuth 流程获取 CSRFToken
        # 这样 session 在 need_verify=True 时也可用
        oauth_result = self._finish_oauth(callback_url)
        if not oauth_result:
            return oauth_result

        if not need_verify:
            return oauth_result

        # 需要设备验证 → 不自动获取设备列表（ getPageInfo 会触发服务端发送验证码）
        # 只返回 need_verify=True 和已有 cookies（含 CSRFToken）
        # 等用户显式调用 send_verify_code() 时再获取设备列表
        return LoginResult(
            success=True,
            need_verify=True,
            cookies=oauth_result.cookies,
        )

    def _step_get_auth_devices(self) -> LoginResult:
        """获取验证设备列表

        此方法由 send_verify_code() 自动调用。
        注意：调用 getPageInfo 会触发服务端向默认设备发送验证码。
        """
        auth_url = (
            f"https://id1.cloud.huawei.com/CAS/portal/authIdentify.html"
            f"?loginUrl={urllib.parse.quote(_SERVICE, safe='')}"
            f"&service={urllib.parse.quote(_SERVICE, safe='')}"
            f"&lang={_LANG}"
            f"&reqClientType={_REQ_CLIENT_TYPE}"
            f"&loginChannel={_LOGIN_CHANNEL}&scenesType=0"
        )
        self.session.get(auth_url)

        self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/common/getBaseSwitchInfo',
            {'themeName': 'huawei', 'lang': _LANG, 'supportHarmonyTheme': 'false'},
        )

        url_param_auth = (
            f'loginUrl={urllib.parse.quote(_SERVICE, safe="")}'
            f'&service={urllib.parse.quote(_SERVICE, safe="")}'
            f'&lang={_LANG}'
            f'&reqClientType={_REQ_CLIENT_TYPE}'
            f'&loginChannel={_LOGIN_CHANNEL}&scenesType=0'
        )
        resp = self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/cloudIframeAuthIdentify/getPageInfo',
            {
                'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
                'lang': _LANG, 'languageCode': _LANG,
                'loginUrl': _SERVICE, 'service': _SERVICE,
                'scenesType': '0', 'pageName': 'cloudIframeAuthIdentify',
                'interfaceName': 'cloudIframeAuthIdentify/getPageInfo',
                'supportHarmonyTheme': 'false', 'urlParam': url_param_auth,
            },
            referer=auth_url,
        )
        auth_result = resp.json()

        if auth_result.get('isSuccess') != 1:
            return LoginResult(False, error='获取验证设备列表失败', detail=auth_result)

        self._auth_page_token = auth_result.get('pageToken', '')
        self._auth_page_token_key = auth_result.get('pageTokenKey', '')

        # 认证页面也需要 dev + analysisHealth 步骤（与浏览器行为一致）
        # 服务端要求在提交 cloudAuthLogin 前完成这些步骤
        self._step_auth_dev()
        self._step_auth_health(auth_url)

        error_desc_str = auth_result.get('localInfo', {}).get('errorDesc', '{}')
        error_desc = json.loads(error_desc_str) if isinstance(error_desc_str, str) else error_desc_str
        auth_devices = error_desc.get('authCodeSentList', [])
        self._auth_devices = auth_devices

        return LoginResult(
            success=True,
            need_verify=True,
            cookies=self._get_cookies_dict(),
            auth_devices=auth_devices,
        )

    def _step_auth_dev(self) -> None:
        """认证页面的设备指纹步骤（使用 auth pageToken）"""
        fp_value = _generate_fp()
        dev_data: Dict[str, Any] = {
            'pageToken': self._auth_page_token, 'pageTokenKey': self._auth_page_token_key,
            'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
            'lang': _LANG, 'languageCode': _LANG,
            'fp': fp_value,
        }
        if self._saved_hwid:
            dev_data['hwid_cas_sid'] = self._saved_hwid
        resp = self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/dev', dev_data,
        )
        try:
            dev_result = resp.json()
            dev_sid = dev_result.get('sid', '')
            if dev_sid:
                self._saved_hwid = dev_sid
        except Exception:
            pass

    def _step_auth_health(self, referer: str = '') -> None:
        """认证页面的健康检测步骤（使用 auth pageToken）"""
        self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/analysisHealth',
            {
                'pageToken': self._auth_page_token, 'pageTokenKey': self._auth_page_token_key,
                'reqClientType': _REQ_CLIENT_TYPE, 'loginChannel': _LOGIN_CHANNEL,
                'lang': _LANG, 'languageCode': _LANG,
                'operType': '1000',
                'message': json.dumps({
                    "currentUri": "/CAS/portal/authIdentify.html",
                    "isOpenCookie": "true", "isOpenPerformance": True,
                    "isSupportES6": True, "dNSTake": "0", "tCPTake": "0",
                    "reqRespTake": "92", "totalTake": "1523", "whiteScreenTake": "102",
                    "resourceDataSize": 1124977, "domDisplayTake": "391",
                    "reqReadyTake": "10",
                    "currentLocaleTime": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "resources": [], "extInfo": {"isSwitchWiseContent2SLB": False}
                }),
                'illnessType': '0', 'isIframe': 'true', 'service': _SERVICE,
            },
            referer=referer,
        )

    def _finish_oauth(self, callback_url: str) -> LoginResult:
        """ticket换session → OAuth → 完成登录"""
        if not callback_url:
            return LoginResult(False, error='callbackURL为空')

        resp = self.session.get(callback_url, allow_redirects=False)
        if resp.status_code != 302:
            return LoginResult(False, error='ticket换取失败')

        oauth_url = resp.headers.get('Location', '')
        if not oauth_url:
            return LoginResult(False, error='未获取到OAuth重定向URL')

        self.session.get(oauth_url, allow_redirects=False)

        parsed = urllib.parse.urlparse(oauth_url)
        params = urllib.parse.parse_qs(parsed.query)
        redirect_uri = params.get('redirect_uri', [''])[0]
        scope = params.get('scope', [''])[0]

        resp = self.session.post(
            f'https://oauth-login.cloud.huawei.com/oauth2/ajax/getLoginWay?reflushCode={self._reflush()}',
            data={
                'response_type': 'code', 'client_id': _CLIENT_ID,
                'redirect_uri': redirect_uri, 'access_type': 'offline',
                'scope': scope, 'lang': params.get('lang', [''])[0] or _LANG,
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'interfaceVersion': 'v3', 'fromLoginAuth': 'false',
                'Origin': 'https://oauth-login.cloud.huawei.com',
            },
        )
        oauth_result = resp.json()
        if oauth_result.get('isSuccess') != 'true':
            return LoginResult(False, error='getLoginWay失败', detail=oauth_result)

        sig_info = oauth_result.get('signatureInfo', {})
        cas_redirect_url = (
            oauth_result.get('loginInteractInfo', {}).get('cas', {}).get('casLoginRedirectUrl', '')
        )
        if not cas_redirect_url:
            return LoginResult(False, error='未获取到casLoginRedirectUrl')

        resp = self.session.get(cas_redirect_url, allow_redirects=False)
        login_callback_url = resp.headers.get('Location', '') if resp.status_code == 302 else resp.url

        # 必须访问 loginCallback 页面，服务端需要验证 ticket 并建立 OAuth 授权状态
        # 跳过此步骤会导致 oauth2/ajax/login 报错 "missing required parameter: token"
        if login_callback_url:
            self.session.get(login_callback_url, allow_redirects=False)

        cb_params = urllib.parse.parse_qs(urllib.parse.urlparse(login_callback_url).query)
        ticket = cb_params.get('ticket', [''])[0]
        site_id = cb_params.get('siteID', ['1'])[0]
        country_code = cb_params.get('countryCode', ['CN'])[0]

        oauth_host = (
            'oauth-login1.cloud.huawei.com'
            if 'oauth-login1' in login_callback_url
            else 'oauth-login.cloud.huawei.com'
        )

        resp = self.session.post(
            f'https://{oauth_host}/oauth2/ajax/login?reflushCode={self._reflush()}&display=page',
            data={
                'access_type': sig_info.get('access_type', 'offline'),
                'client_id': sig_info.get('client_id', _CLIENT_ID),
                'code_challenge_method': sig_info.get('code_challenge_method', 'S256'),
                'display': sig_info.get('display', 'page'),
                'flowID': sig_info.get('flowID', ''),
                'h': sig_info.get('h', ''),
                'include_granted_scopes': sig_info.get('include_granted_scopes', 'true'),
                'lang': sig_info.get('lang', _LANG),
                'nonce': sig_info.get('nonce', 'default'),
                'prompt': sig_info.get('prompt', 'login'),
                'redirect_uri': sig_info.get('redirect_uri', 'https://cloud.huawei.com:443/homeTransit'),
                'response_type': sig_info.get('response_type', 'code'),
                'scope': sig_info.get('scope', ''),
                'v': sig_info.get('v', ''),
                'ticket': ticket, 'siteID': site_id, 'countryCode': country_code,
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'interfaceVersion': 'v3', 'fromLoginAuth': 'false',
                'Origin': f'https://{oauth_host}',
            },
        )
        login_data = resp.json()
        if login_data.get('isSuccess') != 'true':
            return LoginResult(False, error='OAuth login失败', detail=login_data)

        code_url = login_data.get('code', '')
        resp = self.session.get(code_url, allow_redirects=False)
        if resp.status_code == 302:
            # homeTransit 返回 302，Set-Cookie 设置 needActive、userId
            # 不再跟随重定向到 /home，因为 /home 中的 isLogin/CSRFToken 等
            # cookies 是由前端 JS 通过 document.cookie 设置的，requests 无法执行 JS
            # 我们改用服务端 API 来获取这些值
            pass
        elif resp.status_code == 200:
            # 某些情况下 homeTransit 直接返回 200（不太常见但需要处理）
            pass

        # Step A: 跟随 homeTransit 重定向到 /home — 获取初始 CSRFToken
        self._fetch_initial_csrf()

        # Step B: getHomeData — 轮换 CSRFToken，获取 loginSecLevel/functionSupport 等
        self._fetch_home_data()

        # Step C: queryCookieValuesByNames — 获取服务端已知 cookie 值
        self._fetch_server_cookies()

        # Step D: heartbeatCheck — 再次轮换 CSRFToken（可选，保持 token 新鲜）
        self._fetch_csrf_via_heartbeat()

        cookies = self._get_cookies_dict()
        # 登录成功（cookie 仍有效），保存指纹
        _save_fingerprint(_fp_cache)
        return LoginResult(
            success=True,
            need_verify=False,
            cookies=cookies,
        )

    def _fetch_initial_csrf(self) -> None:
        """获取初始 CSRFToken

        跟随 homeTransit 的 302 重定向到 /home，
        服务端会通过 Set-Cookie 和响应头设置初始 CSRFToken。
        """
        try:
            resp = self.session.get(
                'https://cloud.huawei.com/home',
                allow_redirects=True,
                timeout=30,
                verify=False,
            )
            if resp.status_code == 200:
                # 从响应头获取 CSRFToken
                csrf_from_header = resp.headers.get('CSRFToken', '')
                if csrf_from_header:
                    self.session.cookies.set('CSRFToken', csrf_from_header, domain='cloud.huawei.com')
                    logger.debug("GET /home 成功，初始 CSRFToken: %s", csrf_from_header[:16])
            else:
                logger.warning("GET /home 返回状态码: %s", resp.status_code)
        except Exception as e:
            logger.warning("GET /home 失败: %s", e)

    def _fetch_home_data(self) -> None:
        """调用 getHomeData API 轮换 CSRFToken 并获取登录状态 cookies

        getHomeData 会：
        1. 验证当前 CSRFToken
        2. 返回新的 CSRFToken（轮换）
        3. 设置 loginSecLevel、isLogin、functionSupport、webOfficeEditToken、shareToken
        """
        csrf_token = ''
        for cookie in self.session.cookies:
            if cookie.name == 'CSRFToken' and cookie.value:
                csrf_token = cookie.value
                break
        if not csrf_token:
            logger.warning("getHomeData 缺少 CSRFToken，跳过")
            return

        try:
            trace_id = f"00001_02_{int(time.time())}_{random.randint(10000000, 99999999)}"
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json;charset=UTF-8',
                'Origin': 'https://cloud.huawei.com',
                'Referer': 'https://cloud.huawei.com/home',
                'x-hw-device-category': 'Web',
                'x-hw-os-brand': 'Web',
                'x-hw-client-mode': 'frontend',
                'x-hw-device-type': '7',
                'x-hw-trace-id': trace_id,
            }
            resp = self.session.post(
                f"https://cloud.huawei.com/html/getHomeData?traceId={trace_id}",
                headers=headers,
                json={'traceId': trace_id},
                timeout=30,
                verify=False,
            )
            if resp.status_code == 200:
                # getHomeData 响应头会设置新的 CSRFToken 和其他 cookies
                csrf_from_header = resp.headers.get('CSRFToken', '')
                if csrf_from_header:
                    self.session.cookies.set('CSRFToken', csrf_from_header, domain='cloud.huawei.com')
                    logger.debug("getHomeData 成功，轮换后 CSRFToken: %s", csrf_from_header[:16])
                else:
                    logger.debug("getHomeData 成功")
            else:
                logger.warning("getHomeData 返回状态码: %s", resp.status_code)
        except Exception as e:
            logger.warning("getHomeData 失败: %s", e)

    def _fetch_csrf_via_heartbeat(self) -> None:
        """通过 heartbeatCheck 轮换 CSRFToken

        在获取初始 CSRFToken 后，heartbeatCheck 用于轮换 token 保持新鲜。
        注意：heartbeatCheck 需要 Cookie 中已存在 CSRFToken 并在请求头中携带。
        """
        csrf_token = ''
        for cookie in self.session.cookies:
            if cookie.name == 'CSRFToken' and cookie.value:
                csrf_token = cookie.value
                break
        if not csrf_token:
            logger.warning("heartbeatCheck 缺少 CSRFToken，跳过")
            return

        user_id = ''
        for cookie in self.session.cookies:
            if cookie.name == 'userId' and cookie.value:
                user_id = cookie.value
                break

        try:
            trace_id = f"07100_02_{int(time.time())}_{random.randint(10000000, 99999999)}"
            url = f"https://cloud.huawei.com/heartbeatCheck?checkType=1&traceId={trace_id}"
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'CSRFToken': csrf_token,
                'userId': user_id,
                'x-hw-device-category': 'Web',
                'x-hw-os-brand': 'Web',
                'x-hw-client-mode': 'frontend',
                'x-hw-device-type': '7',
                'Referer': 'https://cloud.huawei.com/home',
            }
            resp = self.session.get(url, headers=headers, timeout=30, verify=False)
            if resp.status_code == 200:
                # 从响应头获取新的 CSRFToken
                csrf_from_header = resp.headers.get('CSRFToken', '')
                if csrf_from_header:
                    self.session.cookies.set('CSRFToken', csrf_from_header, domain='cloud.huawei.com')
                    logger.debug("heartbeatCheck 成功，新 CSRFToken: %s", csrf_from_header[:16])
            else:
                logger.warning("heartbeatCheck 返回状态码: %s", resp.status_code)
        except Exception as e:
            logger.warning("heartbeatCheck 失败: %s", e)

    def _fetch_server_cookies(self) -> None:
        """从服务端 API 获取浏览器端 JS 设置的 cookie 值

        浏览器中 /home 页面的 JS 会设置 isLogin、loginSecLevel、functionSupport、
        webOfficeEditToken、shareToken 等 cookies。这些值来自服务端数据，
        但 requests 无法执行 JS。

        通过 queryCookieValuesByNames API 获取服务端已知的 cookie 值，
        然后手动设置到 session 中。
        """
        try:
            # queryCookieValuesByNames 不需要 CSRFToken 头（只需要 userId）
            # 但如果已有 CSRFToken 会更好
            csrf_token = ''
            for cookie in self.session.cookies:
                if cookie.name == 'CSRFToken' and cookie.value:
                    csrf_token = cookie.value
                    break
            user_id = ''
            for cookie in self.session.cookies:
                if cookie.name == 'userId' and cookie.value:
                    user_id = cookie.value
                    break

            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json;charset=UTF-8',
                'Origin': 'https://cloud.huawei.com',
                'Referer': 'https://cloud.huawei.com/home',
            }
            if csrf_token:
                headers['CSRFToken'] = csrf_token
                headers['csrftoken'] = csrf_token
            if user_id:
                headers['userId'] = user_id

            trace_id = f"25001_02_{int(time.time())}_{random.randint(10000000, 99999999)}"
            resp = self.session.post(
                f"https://cloud.huawei.com/html/queryCookieValuesByNames?traceId={trace_id}",
                headers=headers,
                json={},
                timeout=30,
                verify=False,
            )
            if resp.status_code == 200:
                data = resp.json()
                server_cookies = data.get('cookies', {})
                if server_cookies:
                    for name, value in server_cookies.items():
                        if value is not None:
                            self.session.cookies.set(str(name), str(value), domain='cloud.huawei.com')
                    logger.debug("queryCookieValuesByNames 获取 %d 项 cookies", len(server_cookies))
            else:
                logger.debug("queryCookieValuesByNames 返回状态码: %s", resp.status_code)
        except Exception as e:
            logger.debug("queryCookieValuesByNames 失败: %s", e)

        # 确保 isLogin=1 被设置（即使 queryCookieValuesByNames 没返回）
        has_is_login = False
        for cookie in self.session.cookies:
            if cookie.name == 'isLogin':
                has_is_login = True
                break
        if not has_is_login:
            self.session.cookies.set('isLogin', '1', domain='cloud.huawei.com')

    # ==================== Cookie 管理 ====================

    def _clear_oauth_session_cookies(self) -> None:
        """清除第一次 OAuth 流程设置的干扰 cookies

        当 login() 返回 need_verify=True 时，_step_password_login 已经走了一遍
        _finish_oauth，设置了 cloud.huawei.com 域的 JSESSIONID、loginID、token 等 cookies。
        verify_device 再次调用 _finish_oauth 时，这些旧 cookies 会导致 OAuth login 失败
        （服务端可能误判为已授权或使用过期的 loginID/token）。

        需要清除的 cookies：
        - cloud.huawei.com 域: JSESSIONID, loginID, token（第一次 OAuth 设置的）
        - .huawei.com 域: CASLOGINSITE, LOGINACCSITE, HuaweiID_CAS_ISCASLOGIN（可能被旧值覆盖）

        保留的 cookies：
        - id1 域: CASTGC, JSESSIONID, hwid_cas_sid, sid 等（认证流程需要的）
        - cloud.huawei.com 域: userId, isLogin, CSRFToken, loginSecLevel 等（session 状态）
        """
        # 清除 cloud.huawei.com 域的 OAuth 会话 cookies
        # JSESSIONID 可能没有显式 Domain（domain_specified=False），
        # loginID/token 有 Domain=cloud.huawei.com
        to_remove = []
        for cookie in self.session.cookies:
            is_cloud_domain = (
                cookie.domain == 'cloud.huawei.com'
                or (cookie.domain and cookie.domain.endswith('.cloud.huawei.com'))
            )
            if is_cloud_domain and cookie.name in ('JSESSIONID', 'loginID', 'token'):
                to_remove.append(cookie)
        for cookie in to_remove:
            self.session.cookies.clear(cookie.domain, cookie.path, cookie.name)

    def _get_cookies_dict(self) -> Dict[str, str]:
        return {c.name: c.value for c in self.session.cookies}

    def _apply_login_cookies(self, cookies: Dict[str, str]) -> None:
        """将之前保存的 cookies 应用到 session，根据 cookie 名称分配正确的 domain

        重要：当 cookies 过期后重新登录时，需要清除旧的会话级 cookies
        （如 CASTGC、JSESSIONID、isLogin、CSRFToken 等），因为它们已经失效，
        如果保留会被服务端误判为已登录用户，导致使用过期的 TGT 换取 ticket，
        从而使登录流程失败。只保留设备信任标识（hwid_cas_sid/sid）和
        登录渠道相关的 cookies。
        """
        for name, value in cookies.items():
            if name.startswith('remember_client_flag'):
                self.session.cookies.set(name, value, domain='.id1.cloud.huawei.com')
            elif name in _ID1_SESSION_COOKIE_KEYS:
                # 跳过旧的 id1 会话级 cookies，让服务端在重新登录时重新签发
                logger.debug("跳过旧 id1 会话 cookie: %s", name)
                continue
            elif name in _CLOUD_SESSION_COOKIE_KEYS:
                # 跳过旧的 cloud.huawei.com 会话级 cookies，
                # 这些在过期后无效，保留会干扰服务端判断登录状态
                logger.debug("跳过旧 cloud 会话 cookie: %s", name)
                continue
            elif name in ('hwid_cas_sid', 'sid'):
                # 设备信任标识 — 这是最关键的 cookie，用于让服务端识别受信任设备
                self.session.cookies.set(name, value, domain='.id1.cloud.huawei.com')
            elif name in _ID1_COOKIE_KEYS:
                # 其他 id1 域 cookies（如 cplang、HW_* 分析 cookies）
                self.session.cookies.set(name, value, domain='.id1.cloud.huawei.com')
            elif name in _HUAWEI_COM_COOKIE_KEYS:
                self.session.cookies.set(name, value, domain='.huawei.com')
            elif name in _CLOUD_HUAWEI_COM_COOKIE_KEYS:
                # cloud.huawei.com 域的 cookies
                self.session.cookies.set(name, value, domain='cloud.huawei.com')
            else:
                # 未知 cookie：不盲设 domain，记录警告，仅在值有效时设置
                logger.warning(
                    '未知 cookie "%s" 被忽略，无法确定正确的域。'
                    '已知域: cloud.huawei.com / .id1.cloud.huawei.com / .huawei.com。'
                    '如为有效 cookie，请更新 _CLOUD_HUAWEI_COM_COOKIE_KEYS 等常量。',
                    name,
                )
