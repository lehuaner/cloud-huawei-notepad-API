"""华为云空间登录模块

两种登录场景:
1. 信任设备: login(cookies=...) → need_verify=False, 直接获得 cookies
2. 新设备:   login() → need_verify=True, 需调用 verify_device(code)

登录完成后，用户应保存 cookies，下次直接使用 cookies 登录即可跳过设备验证。
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

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ===================== 工具函数 =====================

def _sha1_hex(data: str) -> str:
    return hashlib.sha1(data.encode('utf-8')).hexdigest()


def _generate_fp() -> str:
    """生成设备指纹 (与前端 JS 逻辑一致)"""
    fingerprint = {
        'canvas': _sha1_hex('canvas_fingerprint_placeholder_chrome_windows'),
        'webgl': _sha1_hex('webgl_fingerprint_placeholder_angle_intel'),
        'epl': '5',
        'ep': _sha1_hex('PDF Viewer,Chrome PDF Viewer,Chromium PDF Viewer,Microsoft Edge PDF Viewer,WebKit built-in PDF'),
        'epls': 'C' + _sha1_hex('Chrome PDF Plugin,Chrome PDF Viewer,Portable Document Format'),
        'fonts': _sha1_hex('Arial,Courier New,Georgia,Impact,Times New Roman,Verdana'),
        'nacn': 'Mozilla', 'nan': 'Netscape', 'nce': 'true', 'nlg': 'zh-CN',
        'npf': 'Win32', 'sah': '1040', 'saw': '1920', 'sh': '1080', 'sw': '1920',
        'bsh': '0', 'bsw': '0', 'ett': str(int(time.time() * 1000)), 'etz': '-480',
    }
    parts = []
    for key in sorted(fingerprint.keys()):
        val = fingerprint[key]
        if val:
            parts.append(f'{urllib.parse.quote(key, safe="")}={urllib.parse.quote(str(val), safe="")}')
    serialized = '&'.join(parts)
    checksum = _sha1_hex(serialized)
    data_with_cs = serialized + '&cs=' + checksum
    xor_key = 211
    encrypted_chars = []
    for ch in data_with_cs:
        encrypted_byte = (ord(ch) ^ (xor_key - 1)) & 0xFF
        encrypted_chars.append(chr(encrypted_byte))
        xor_key = encrypted_byte
    encrypted = ''.join(encrypted_chars)
    return base64.b64encode(encrypted.encode('latin-1')).decode('ascii')


# ===================== 数据类 =====================

@dataclass
class LoginResult:
    """登录结果

    用法::

        result = auth.login(phone, pwd)
        if not result:
            print(result.error)
        elif result.need_verify:
            code = input("验证码: ")
            result = auth.verify_device(code)
        # 保存 cookies 即可，cookies 中已包含信任设备信息
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

    def verify_device(self, verify_code: str) -> LoginResult:
        """提交设备验证码，完成登录

        Args:
            verify_code: 设备上收到的验证码

        Returns:
            LoginResult — 成功后 cookies 已填充（含信任设备信息）
        """
        device = None
        for d in self._auth_devices:
            if d.get('sent') == 1:
                device = d
                break
        if device is None and self._auth_devices:
            device = self._auth_devices[0]
        if device is None:
            return LoginResult(False, error='没有可用的验证设备')

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
                'verifyUserAccount': urllib.parse.quote(verify_account_name, safe=''),
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

        return self._finish_oauth(auth_result.get('callbackURL', ''))

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

        is_need_image_code = 0
        # 图片验证码处理 (需要时)
        # if is_need_image_code == 1: ...

        resp = self._post_form(
            'https://id1.cloud.huawei.com/CAS/IDM_W/ajaxHandler/remoteLogin', login_data,
        )
        login_result = resp.json()

        # 验证码错误重试
        retry_count = 0
        while login_result.get('errorCode') == '10000201' and retry_count < 3:
            retry_count += 1
            # TODO: 图片验证码重试逻辑
            break

        if login_result.get('isSuccess') != 1:
            return LoginResult(False, error='密码登录失败', detail=login_result)

        need_verify = bool(login_result.get('needPopTrust', False))

        if not need_verify:
            return self._finish_oauth(login_result.get('callbackURL', ''))

        # 需要二次验证 → 获取设备列表
        return self._step_get_auth_devices()

    def _step_get_auth_devices(self) -> LoginResult:
        """获取验证设备列表"""
        auth_url = (
            f"https://id1.cloud.huawei.com/CAS/portal/authIdentify.html"
            f"?loginUrl={urllib.parse.quote(_SERVICE, safe='')}"
            f"&service={urllib.parse.quote(_SERVICE, safe='')}"
            f"&lang={_LANG}"
            f"&reqClientType={_REQ_CLIENT_TYPE}"
            f"&loginChannel={_LOGIN_CHANNEL}&scenesType=0"
        )
        self.session.get(auth_url)

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
            # homeTransit 返回 302，会设置 needActive、userId 等 cookies
            home_url = resp.headers.get('Location', '')
            if home_url:
                target = home_url if home_url.startswith('http') else f"https://cloud.huawei.com{home_url}"
                # 访问 /home 页面，服务端会设置 isLogin=1、CSRFToken 等关键 cookies
                home_resp = self.session.get(target)

                # 如果 /home 响应头中有 Set-Cookie，确保 CSRFToken 被捕获
                # 有些情况下 CSRFToken 在响应头中设置但 requests 可能没有正确保存
                csrf_from_header = home_resp.headers.get('CSRFToken', '')
                if csrf_from_header:
                    self.session.cookies.set('CSRFToken', csrf_from_header, domain='cloud.huawei.com')
        elif resp.status_code == 200:
            # 某些情况下 homeTransit 直接返回 200（不太常见但需要处理）
            pass

        cookies = self._get_cookies_dict()
        return LoginResult(
            success=True,
            need_verify=False,
            cookies=cookies,
        )

    # ==================== Cookie 管理 ====================

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
                # 其他 cookie（如分析追踪类）设置到 .huawei.com
                self.session.cookies.set(name, value, domain='.huawei.com')
