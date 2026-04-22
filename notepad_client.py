# -*- coding: utf-8 -*-
"""
华为云备忘录 API 客户端
使用方式:
    client = NotepadClient(cookies_file="cookies.json")
    result = client.get_tags()
"""
import requests
import json
import os
import time
import random
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEVICE_ID = "7c239f801ac3b3d762d4dc4e88a8bbfaf470c68285dae1db36b1700d200fbe21"


def _generate_traceid(prefix="03135"):
    random_part = ''.join(str(random.randint(1, 9)) for _ in range(8))
    return f"{prefix}_02_{int(time.time())}_{random_part}"


def _generate_new_note_guid():
    """生成新笔记的 guid，格式: newNote{4位hex}-{timestamp毫秒}-{5位随机数}"""
    hex_prefix = ''.join(random.choices('0123456789abcdef', k=4))
    ts = int(time.time() * 1000)
    rand5 = ''.join(str(random.randint(0, 9)) for _ in range(5))
    return f"newNote{hex_prefix}-{ts}-{rand5}"


def _generate_version_hex():
    """生成 currentNotePadVersion 前缀，4位hex"""
    return ''.join(random.choices('0123456789abcdef', k=4))


class NotepadClient:
    """华为云备忘录客户端"""

    def __init__(self, cookies_file=None, cookies_dict=None):
        """
        创建客户端

        Args:
            cookies_file: cookies JSON 文件路径 (如 "cookies.json")
            cookies_dict: cookies 字典 {name: value}，与 cookies_file 二选一
        """
        if cookies_dict:
            self._cookies_dict = cookies_dict
        elif cookies_file:
            self._cookies_file = os.path.abspath(cookies_file)
            with open(self._cookies_file, 'r', encoding='utf-8') as f:
                self._cookies_dict = json.load(f)
        else:
            raise ValueError("必须提供 cookies_file 或 cookies_dict")

        self._cookies_list = self._parse_cookies(self._cookies_dict)
        self._csrf_token = self._get_cookie_value("CSRFToken")
        self._user_id = self._get_cookie_value("userId")
        self._session = requests.Session()
        self._init_session_cookies()
        self._start_cursor = "0"

    @staticmethod
    def _parse_cookies(data):
        """统一解析为 [{name, value}, ...]"""
        if isinstance(data, list):
            return data
        result = []
        for k, v in data.items():
            if isinstance(v, dict) and "value" in v:
                result.append({"name": k, "value": v["value"]})
            else:
                result.append({"name": k, "value": str(v)})
        return result

    def _get_cookie_value(self, name):
        return next((c["value"] for c in self._cookies_list if c["name"] == name), "")

    def _headers(self):
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
            "x-hw-device-id": DEVICE_ID,
            "x-hw-device-manufacturer": "HUAWEI",
            "x-hw-device-type": "7",
            "x-hw-os-brand": "Web",
            "referer": "https://cloud.huawei.com/home",
            "origin": "https://cloud.huawei.com",
        }

    def _cookies_map(self):
        return {c["name"]: c["value"] for c in self._cookies_list}

    def _init_session_cookies(self):
        """将 cookies 列表设置到 Session 的 cookie jar 中"""
        for c in self._cookies_list:
            self._session.cookies.set(c["name"], c["value"], domain="cloud.huawei.com")

    def _sync_cookies_from_response(self, resp):
        """从响应的 Set-Cookie 或 cookie jar 中同步更新关键 cookie"""
        # requests.Session 自动将 Set-Cookie 存入 session.cookies
        # 需要把关键 cookie 同步回内部状态
        jar = self._session.cookies
        for name in ["CSRFToken", "shareToken", "JSESSIONID"]:
            value = jar.get(name, domain="cloud.huawei.com")
            if value:
                # 更新 _cookies_list
                found = False
                for c in self._cookies_list:
                    if c["name"] == name:
                        c["value"] = value
                        found = True
                        break
                if not found:
                    self._cookies_list.append({"name": name, "value": value})
                # 同步到 _cookies_dict（兼容列表和字典格式）
                if isinstance(self._cookies_dict, dict):
                    self._cookies_dict[name] = value
                # 列表格式已在 _cookies_list 中更新，无需额外处理
                if name == "CSRFToken":
                    self._csrf_token = value

    def _post(self, url, body, trace_prefix="03135", timeout=30):
        body["traceId"] = _generate_traceid(trace_prefix)
        try:
            resp = self._session.post(
                url,
                headers=self._headers(),
                json=body,
                timeout=timeout,
                verify=False,
            )
            self._sync_cookies_from_response(resp)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                return {"error": "认证失败(401)，cookies 已过期，请重新从浏览器导出 cookies", "detail": resp.text[:200], "_code": "401"}
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:200], "_code": str(resp.status_code)}
        except Exception as e:
            return {"error": "请求异常", "detail": str(e), "_code": "-1"}

    def _get(self, url, trace_prefix="03135", params=None):
        """通用 GET 请求"""
        try:
            resp = self._session.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=30,
                verify=False,
            )
            self._sync_cookies_from_response(resp)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                return {"error": "认证失败(401)，cookies 已过期，请重新从浏览器导出 cookies", "detail": resp.text[:200], "_code": "401"}
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:200], "_code": str(resp.status_code)}
        except Exception as e:
            return {"error": "请求异常", "detail": str(e), "_code": "-1"}

    @staticmethod
    def _get_code(data):
        """统一提取 code: 支持顶层 code 或 Result.code"""
        if "code" in data:
            return str(data["code"])
        return str(data.get("Result", {}).get("code", ""))

    def _update_start_cursor(self, data):
        """从响应中提取 startCursor 并更新内部状态"""
        cursor = data.get("startCursor", "")
        if cursor:
            self._start_cursor = str(cursor)

    # ========== 基础 API ==========

    def get_common_param(self):
        """获取通用参数"""
        data = self._post("https://cloud.huawei.com/html/getCommonParam", {}, "00001")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code, "msg": "通用参数" if code == "0" else f"失败({code})", "data": data}

    def get_home_data(self):
        """获取首页数据"""
        data = self._post("https://cloud.huawei.com/html/getHomeData", {}, "00001")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code, "msg": "首页数据" if code == "0" else f"失败({code})", "data": data}

    def get_cookies(self, save_to=None):
        """查询 Cookie 值，可保存到文件"""
        data = self._post("https://cloud.huawei.com/html/queryCookieValuesByNames", {}, "25001")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        cookies = data.get("cookies", {})
        code = self._get_code(data)
        if save_to and code == "0" and cookies:
            with open(save_to, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
        return {"ok": code == "0", "code": code, "msg": f"获取{len(cookies)}项" if code == "0" else f"失败({code})", "data": cookies}

    def heartbeat_check(self):
        """心跳检测，保持会话活跃"""
        trace_id = _generate_traceid("07100")
        url = f"https://cloud.huawei.com/heartbeatCheck?checkType=1&traceId={trace_id}"
        data = self._get(url, "07100")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code, "msg": "心跳正常" if code == "0" else f"失败({code})"}

    def notify_poll(self, tag="0", module="portal", timeout=60):
        """通知轮询，获取服务端变更推送（长轮询接口，默认60s超时）
        code=0: 有新通知; code=102: 长轮询超时（无新通知，属正常）; 其他: 错误
        """
        body = {"tag": tag, "module": module}
        data = self._post("https://cloud.huawei.com/notify", body, "07100", timeout=timeout)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"], "detail": data.get("detail", "")}
        code = self._get_code(data)
        new_tag = data.get("tag", tag)
        if code == "0":
            return {"ok": True, "code": code, "msg": "有新通知", "data": data, "tag": new_tag}
        elif code == "102":
            return {"ok": True, "code": code, "msg": "长轮询超时(无新通知)", "data": data, "tag": new_tag}
        else:
            return {"ok": False, "code": code, "msg": f"失败(code={code})", "data": data, "tag": new_tag}

    def get_space_info(self):
        """获取用户云空间容量等信息（traceId 在 URL 参数中，body 为空）"""
        trace_id = _generate_traceid("07102")
        url = f"https://cloud.huawei.com/nsp/getInfos?traceId={trace_id}"
        try:
            resp = self._session.post(
                url,
                headers=self._headers(),
                timeout=30,
                verify=False,
            )
            self._sync_cookies_from_response(resp)
            if resp.status_code == 200:
                data = resp.json()
            elif resp.status_code == 401:
                return {"ok": False, "code": "401", "msg": "认证失败(401)，cookies 已过期，请重新从浏览器导出 cookies"}
            else:
                return {"ok": False, "code": str(resp.status_code), "msg": f"HTTP {resp.status_code}", "detail": resp.text[:200]}
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}
        # /nsp/getInfos 成功时无 code 字段（_get_code 返回空串），有数据即成功
        code = self._get_code(data)
        ok = code in ("0", "") and "deviceList" in data
        return {"ok": ok, "code": code or "0", "msg": "空间信息" if ok else f"失败({code})", "data": data}

    # ========== 备忘录 API ==========

    def get_tags(self):
        """获取标签列表"""
        data = self._post("https://cloud.huawei.com/notepad/notetag/query", {"index": 0}, "03135")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        rsp = data.get("rspInfo", {})
        tags = []
        for item in rsp.get("backLoglist", []):
            raw = item.get("data", "")
            if isinstance(raw, str) and raw:
                try:
                    obj = json.loads(raw)
                    ct = obj.get("content", {})
                    tags.append({"tagId": ct.get("guid", ""), "tagName": ct.get("name", ""),
                                 "type": ct.get("type", 0)})
                except Exception:
                    pass
        if not tags:
            tags = [{"tagId": t.get("tagId", ""), "tagName": t.get("tagName", "")}
                    for t in rsp.get("noteTagList", [])]
        code = self._get_code(data)
        return {"ok": code == "0", "code": code, "msg": f"{len(tags)}个标签" if code == "0" else f"失败({code})", "data": tags}

    def get_notes_list(self, index=0, status=0, guids=""):
        """获取笔记列表"""
        body = {"index": index, "status": status, "guids": guids}
        data = self._post("https://cloud.huawei.com/notepad/simplenote/query", body, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        self._update_start_cursor(data)
        notes = [{"guid": n.get("guid", ""), "title": n.get("title", ""),
                  "etag": n.get("etag", ""), "kind": n.get("kind", ""),
                  "modified": n.get("modified", 0)}
                 for n in data.get("rspInfo", {}).get("noteList", [])]
        code = self._get_code(data)
        return {"ok": code == "0", "code": code, "msg": f"{len(notes)}条笔记" if code == "0" else f"失败({code})",
                "data": notes}

    def get_note_detail(self, guid, kind="note", start_cursor=None):
        """获取笔记详情"""
        body = {
            "ctagNoteInfo": "",
            "startCursor": start_cursor or self._start_cursor,
            "guid": guid,
            "kind": kind
        }
        data = self._post("https://cloud.huawei.com/notepad/note/query", body, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        self._update_start_cursor(data)
        rsp = data.get("rspInfo", {})
        code = self._get_code(data)
        note_str = rsp.get("data", "")
        note_data = {}
        if isinstance(note_str, str) and note_str:
            try:
                obj = json.loads(note_str)
                ct = obj.get("content", {})
                if isinstance(ct, dict):
                    note_data = {"title": ct.get("data5", ""), "content": ct.get("content", ""),
                                 "html_content": ct.get("html_content", ""),
                                 "modified": ct.get("modified", 0), "created": ct.get("created", 0)}
            except Exception:
                pass
        attachments = rsp.get("attachments", [])
        return {"ok": code == "0", "code": code, "msg": "笔记详情" if code == "0" else f"失败({code})",
                "data": {**note_data, "guid": guid, "etag": rsp.get("etag", ""),
                         "kind": rsp.get("kind", kind),
                         "attachments": attachments, "attachment_count": len(attachments)}}

    def create_note(self, title, content_text, tag_id=""):
        """创建新笔记（使用 /notepad/note/create）"""
        now_ms = int(time.time() * 1000)
        note_guid = _generate_new_note_guid()

        note_content = {
            "filedir": "", "delete_flag": 0, "fold_id": 0, "is_lunar": 0,
            "need_reminded": 0, "prefix_uuid": "", "unstruct_uuid": "",
            "created": now_ms, "data6": "0",
            "data5": json.dumps({"data1": title, "data2": "edit", "data4": "1"}, ensure_ascii=False),
            "content": f"Text|{content_text}",
            "html_content": f'<note><element type="Text"><hw_font size ="1.0">{title}</hw_font></element>'
                            f'<element type="Text">{content_text}</element></note>',
            "tag_id": tag_id, "modified": now_ms, "unstructure": "[]",
            "first_attach_name": "", "remind_id": "",
            "favorite": 0, "has_attachment": 0, "has_todo": 0,
            "version": "12", "title": f"{title}\n{content_text}",
            "data3": ""
        }

        inner_data = json.dumps({
            "guid": note_guid, "simpleNote": "", "fileList": [],
            "content": note_content,
            "currentNotePadVersion": f"{_generate_version_hex()}-{now_ms}-{random.randint(10000, 99999)}"
        }, ensure_ascii=False)

        body = {
            "reqInfo": {
                "kind": "note",
                "data": inner_data,
                "guid": note_guid,
                "simpleNote": ""
            },
            "ctagNoteInfo": "",
            "startCursor": self._start_cursor,
            "guid": note_guid,
            "traceId": _generate_traceid("03131")
        }

        try:
            resp = self._session.post(
                "https://cloud.huawei.com/notepad/note/create",
                headers=self._headers(),
                json=body, timeout=30, verify=False
            )
            self._sync_cookies_from_response(resp)
            if resp.status_code != 200:
                return {"ok": False, "code": str(resp.status_code), "msg": f"HTTP {resp.status_code}"}
            result = resp.json()
            code = str(result.get("Result", {}).get("code", "-1"))
            self._update_start_cursor(result)
            rsp = result.get("rspInfo", {})
            real_guid = rsp.get("guid", note_guid)
            return {"ok": code == "0", "code": code,
                    "msg": "创建成功" if code == "0" else f"失败({code})",
                    "data": {"guid": real_guid, "etag": rsp.get("etag", ""),
                             "needSync": result.get("needSync", 0)}}
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def update_note(self, guid, etag, title, content_text, tag_id="", created_time=None, start_cursor=None):
        """
        更新笔记（使用 /notepad/note/update）

        Args:
            guid: 笔记ID
            etag: 版本号（从 get_note_detail 获取）
            title: 标题
            content_text: 正文
            tag_id: 标签ID
            created_time: 创建时间(ms)
            start_cursor: 分页游标
        """
        now_ms = int(time.time() * 1000)

        note_content = {
            "filedir": "", "delete_flag": 0, "fold_id": 0, "is_lunar": 0,
            "need_reminded": 0, "prefix_uuid": guid[:36] if guid else "",
            "unstruct_uuid": "", "created": created_time or now_ms, "data6": "0",
            "data5": json.dumps({"data1": title, "data2": "edit", "data4": "1"}, ensure_ascii=False),
            "content": f"Text|{content_text}",
            "html_content": f'<note><element type="Text"><hw_font size ="1.0">{title}</hw_font></element>'
                            f'<element type="Text">{content_text}</element></note>',
            "tag_id": tag_id, "modified": now_ms, "unstructure": "[]",
            "first_attach_name": "", "remind_id": "",
            "favorite": 0, "has_attachment": 0, "has_todo": 0,
            "version": "12", "title": f"{title}\n{content_text}",
            "data3": ""
        }

        inner_data = json.dumps({
            "guid": guid, "simpleNote": "", "fileList": [],
            "content": note_content,
            "currentNotePadVersion": f"{_generate_version_hex()}-{now_ms}-{random.randint(10000, 99999)}"
        }, ensure_ascii=False)

        body = {
            "reqInfo": {
                "kind": "note",
                "data": inner_data,
                "guid": guid,
                "etag": str(etag),
                "simpleNote": ""
            },
            "ctagNoteInfo": "",
            "startCursor": start_cursor or self._start_cursor,
            "traceId": _generate_traceid("03133")
        }

        try:
            resp = self._session.post(
                "https://cloud.huawei.com/notepad/note/update",
                headers=self._headers(),
                json=body, timeout=30, verify=False
            )
            self._sync_cookies_from_response(resp)
            if resp.status_code != 200:
                return {"ok": False, "code": str(resp.status_code), "msg": f"HTTP {resp.status_code}"}
            if not resp.text:
                return {"ok": True, "code": "0", "msg": "更新成功", "data": {"guid": guid}}
            result = resp.json()
            code = str(result.get("Result", {}).get("code", "-1"))
            self._update_start_cursor(result)
            rsp = result.get("rspInfo", {})
            return {"ok": code == "0", "code": code,
                    "msg": "更新成功" if code == "0" else f"失败({code})",
                    "data": {"guid": rsp.get("guid", guid), "etag": rsp.get("etag", ""),
                             "needSync": result.get("needSync", 0)}}
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}

    def sync(self, ctag_note_info="", ctag_task_info="", start_cursor=None):
        """
        同步操作，在创建/更新笔记后调用

        Args:
            ctag_note_info: 笔记 ctag 信息
            ctag_task_info: 任务 ctag 信息
            start_cursor: 分页游标
        """
        body = {
            "ctagNoteInfo": ctag_note_info,
            "ctagTaskInfo": ctag_task_info,
            "startCursor": start_cursor or self._start_cursor,
            "traceId": _generate_traceid("03131")
        }
        data = self._post("https://cloud.huawei.com/notepad/sync", body, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        self._update_start_cursor(data)
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "同步成功" if code == "0" else f"失败({code})",
                "data": {"needSync": data.get("needSync", 0), "startCursor": data.get("startCursor", "")}}

    def get_task_detail(self, guid, ctag_task_info="", start_cursor=None):
        """
        查询待办任务详情

        Args:
            guid: 任务ID
            ctag_task_info: 任务 ctag 信息
            start_cursor: 分页游标
        """
        body = {
            "ctagTaskInfo": ctag_task_info,
            "startCursor": start_cursor or self._start_cursor,
            "guid": guid,
            "traceId": _generate_traceid("03131")
        }
        data = self._post("https://cloud.huawei.com/notepad/task/query", body, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        self._update_start_cursor(data)
        code = self._get_code(data)
        rsp = data.get("rspInfo", {})
        return {"ok": code == "0", "code": code,
                "msg": "任务详情" if code == "0" else f"失败({code})",
                "data": rsp}

    def get_graffiti_data(self, asset_id, record_id, version_id, kind="newnote"):
        """
        获取涂鸦/手写笔记数据

        Args:
            asset_id: 资产ID
            record_id: 记录ID
            version_id: 版本ID
            kind: 类型，默认 "newnote"
        """
        trace_id = _generate_traceid("03131")
        url = (f"https://cloud.huawei.com/proxyserver/getGraffitiData4V2"
               f"?traceId={trace_id}&assetId={asset_id}&recordId={record_id}"
               f"&versionId={version_id}&kind={kind}")
        data = self._get(url, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "涂鸦数据" if code == "0" else f"失败({code})",
                "data": data}

    def pre_process_file(self, need_to_sign_url="", http_method="GET", generate_sign_flag=False):
        """
        文件预签名，获取附件下载签名URL

        Args:
            need_to_sign_url: 需要签名的URL
            http_method: HTTP 方法，默认 "GET"
            generate_sign_flag: 是否生成签名标志
        """
        body = {
            "needToSignUrl": need_to_sign_url,
            "httpMethod": http_method,
            "generateSignFlag": generate_sign_flag
        }
        data = self._post("https://cloud.huawei.com/proxyserver/driveFileProxy/preProcess", body, "03133")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "预签名成功" if code == "0" else f"失败({code})",
                "data": data}

    def refresh_cookies(self, save_to=None):
        """刷新 cookies（查询后更新本地文件及客户端状态）"""
        data = self._post("https://cloud.huawei.com/html/queryCookieValuesByNames", {}, "25001")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        cookies = data.get("cookies", {})
        code = self._get_code(data)
        if code == "0" and cookies:
            self._cookies_dict = cookies
            self._cookies_list = self._parse_cookies(cookies)
            self._csrf_token = self._get_cookie_value("CSRFToken")
            self._user_id = self._get_cookie_value("userId")
            if save_to:
                with open(save_to, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
            elif hasattr(self, "_cookies_file"):
                with open(self._cookies_file, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
        return {"ok": code == "0", "code": code, "msg": f"刷新{len(cookies)}项" if code == "0" else f"失败({code})"}
