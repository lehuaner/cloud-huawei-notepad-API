"""华为云空间 · 备忘录模块"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any, Dict, List, Optional, Union

from .base import BaseModule, Result, _generate_traceid

logger = logging.getLogger("cloud-space-huawei.notepad")


def _generate_new_note_guid() -> str:
    hex_prefix = ''.join(random.choices('0123456789abcdef', k=4))
    ts = int(time.time() * 1000)
    rand5 = ''.join(str(random.randint(0, 9)) for _ in range(5))
    return f"newNote{hex_prefix}-{ts}-{rand5}"


def _generate_version_hex() -> str:
    return ''.join(random.choices('0123456789abcdef', k=4))


class NotepadModule(BaseModule):
    """华为云备忘录

    通过 HuaweiCloudClient.notepad 访问::

        client = HuaweiCloudClient.from_cookies(cookies)
        notes = client.notepad.get_notes_list()
    """

    # ========== 基础 API ==========

    def get_common_param(self) -> Result:
        """获取通用参数"""
        data = self._post("https://cloud.huawei.com/html/getCommonParam", {}, "00001")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "通用参数" if code == "0" else f"失败({code})", "data": data}

    def get_home_data(self) -> Result:
        """获取首页数据 (含 deviceIdForHeader)"""
        data = self._post("https://cloud.huawei.com/html/getHomeData", {}, "00001")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "首页数据" if code == "0" else f"失败({code})", "data": data}

    def get_cookies(self) -> Result:
        """查询 Cookie 值"""
        data = self._post("https://cloud.huawei.com/html/queryCookieValuesByNames", {}, "25001")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        cookies = data.get("cookies", {})
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": f"获取{len(cookies)}项" if code == "0" else f"失败({code})",
                "data": cookies}

    def heartbeat_check(self) -> Result:
        """心跳检测，保持会话活跃"""
        trace_id = _generate_traceid("07100")
        url = f"https://cloud.huawei.com/heartbeatCheck?checkType=1&traceId={trace_id}"
        data = self._get(url, "07100")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "心跳正常" if code == "0" else f"失败({code})"}

    def notify_poll(self, tag: str = "0", module: str = "portal", timeout: int = 60) -> Result:
        """通知轮询 (长轮询)"""
        body = {"tag": tag, "module": module}
        data = self._post("https://cloud.huawei.com/notify", body, "07100", timeout=timeout)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        new_tag = data.get("tag", tag)
        if code == "0":
            return {"ok": True, "code": code, "msg": "有新通知", "data": data, "tag": new_tag}
        elif code == "102":
            return {"ok": True, "code": code, "msg": "长轮询超时(无新通知)", "data": data, "tag": new_tag}
        else:
            return {"ok": False, "code": code, "msg": f"失败(code={code})", "data": data, "tag": new_tag}

    def get_space_info(self) -> Result:
        """获取用户云空间容量等信息"""
        trace_id = _generate_traceid("07102")
        url = f"https://cloud.huawei.com/nsp/getInfos?traceId={trace_id}"
        data = self._post(url, {}, "07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        ok = code in ("0", "") and "deviceList" in data
        return {"ok": ok, "code": code or "0",
                "msg": "空间信息" if ok else f"失败({code})", "data": data}

    # ========== 备忘录 API ==========

    def get_tags(self) -> Result:
        """获取标签列表"""
        data = self._post("https://cloud.huawei.com/notepad/notetag/query", {"index": 0}, "03135")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        rsp = data.get("rspInfo", {})
        result_data = {"backLoglist": rsp.get("backLoglist", []), "noteList": rsp.get("noteList", [])}
        total = len(result_data["backLoglist"]) + len(result_data["noteList"])
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": f"{total}个标签" if code == "0" else f"失败({code})", "data": result_data}

    def get_notes_list(self, index: int = 0, status: int = 0, guids: str = "") -> Result:
        """获取笔记列表"""
        body: Dict[str, Any] = {"index": index, "status": status, "guids": guids}
        data = self._post("https://cloud.huawei.com/notepad/simplenote/query", body, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        self._update_start_cursor(data)
        rsp = data.get("rspInfo", {})
        result_data = {
            "taskList": rsp.get("taskList", []),
            "discardList": rsp.get("discardList", []),
            "noteList": rsp.get("noteList", []),
        }
        total = len(result_data["taskList"]) + len(result_data["discardList"]) + len(result_data["noteList"])
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": f"{total}条笔记" if code == "0" else f"失败({code})", "data": result_data}

    def get_note_detail(self, guid: str, kind: str = "note", start_cursor: Optional[str] = None) -> Result:
        """获取笔记详情"""
        body: Dict[str, Any] = {
            "ctagNoteInfo": "", "startCursor": start_cursor or self._start_cursor,
            "guid": guid, "kind": kind,
        }
        data = self._post("https://cloud.huawei.com/notepad/note/query", body, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        self._update_start_cursor(data)
        rsp = data.get("rspInfo", {})
        code = self._get_code(data)
        note_str = rsp.get("data", "")
        note_data: Dict[str, Any] = {}
        if isinstance(note_str, str) and note_str:
            try:
                obj = json.loads(note_str)
                ct = obj.get("content", {})
                if isinstance(ct, dict):
                    note_data = {
                        "title": ct.get("data5", ""), "content": ct.get("content", ""),
                        "html_content": ct.get("html_content", ""),
                        "modified": ct.get("modified", 0), "created": ct.get("created", 0),
                    }
            except json.JSONDecodeError:
                logger.debug("笔记详情 JSON 解析失败: %s", note_str[:100])
        attachments = rsp.get("attachments", [])
        return {"ok": code == "0", "code": code,
                "msg": "笔记详情" if code == "0" else f"失败({code})",
                "data": {**note_data, "guid": guid, "etag": rsp.get("etag", ""),
                         "kind": rsp.get("kind", kind),
                         "attachments": attachments, "attachment_count": len(attachments)}}

    def create_note(self, title: str, content_text: str, tag_id: str = "") -> Result:
        """创建新笔记"""
        now_ms = int(time.time() * 1000)
        note_guid = _generate_new_note_guid()

        note_content = {
            "filedir": "", "delete_flag": 0, "fold_id": 0, "is_lunar": 0,
            "need_reminded": 0, "prefix_uuid": "", "unstruct_uuid": "",
            "created": now_ms, "data6": "0",
            "data5": json.dumps({"data1": title, "data2": "edit", "data4": "1"}, ensure_ascii=False),
            "content": f"Text|{content_text}",
            "html_content": (
                f'<note><element type="Text"><hw_font size ="1.0">{title}</hw_font></element>'
                f'<element type="Text">{content_text}</element></note>'
            ),
            "tag_id": tag_id, "modified": now_ms, "unstructure": "[]",
            "first_attach_name": "", "remind_id": "",
            "favorite": 0, "has_attachment": 0, "has_todo": 0,
            "version": "12", "title": f"{title}\n{content_text}", "data3": "",
        }

        inner_data = json.dumps({
            "guid": note_guid, "simpleNote": "", "fileList": [],
            "content": note_content,
            "currentNotePadVersion": f"{_generate_version_hex()}-{now_ms}-{random.randint(10000, 99999)}",
        }, ensure_ascii=False)

        body: Dict[str, Any] = {
            "reqInfo": {"kind": "note", "data": inner_data, "guid": note_guid, "simpleNote": ""},
            "ctagNoteInfo": "", "startCursor": self._start_cursor, "guid": note_guid,
            "traceId": _generate_traceid("03131"),
        }

        try:
            resp = self._request_with_retry(
                "POST", "https://cloud.huawei.com/notepad/note/create",
                headers=self._headers(), json=body, timeout=30, verify=False,
            )
            self._sync_cookies(resp)
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
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}
        except json.JSONDecodeError as e:
            return {"ok": False, "code": "-2", "msg": f"响应解析失败: {e}"}

    def update_note(
        self,
        guid: str,
        etag: Union[str, int],
        title: str,
        content_text: str,
        tag_id: str = "",
        created_time: Optional[int] = None,
        start_cursor: Optional[str] = None,
    ) -> Result:
        """更新笔记"""
        now_ms = int(time.time() * 1000)
        note_content = {
            "filedir": "", "delete_flag": 0, "fold_id": 0, "is_lunar": 0,
            "need_reminded": 0, "prefix_uuid": guid[:36] if guid else "",
            "unstruct_uuid": "", "created": created_time or now_ms, "data6": "0",
            "data5": json.dumps({"data1": title, "data2": "edit", "data4": "1"}, ensure_ascii=False),
            "content": f"Text|{content_text}",
            "html_content": (
                f'<note><element type="Text"><hw_font size ="1.0">{title}</hw_font></element>'
                f'<element type="Text">{content_text}</element></note>'
            ),
            "tag_id": tag_id, "modified": now_ms, "unstructure": "[]",
            "first_attach_name": "", "remind_id": "",
            "favorite": 0, "has_attachment": 0, "has_todo": 0,
            "version": "12", "title": f"{title}\n{content_text}", "data3": "",
        }

        inner_data = json.dumps({
            "guid": guid, "simpleNote": "", "fileList": [],
            "content": note_content,
            "currentNotePadVersion": f"{_generate_version_hex()}-{now_ms}-{random.randint(10000, 99999)}",
        }, ensure_ascii=False)

        body: Dict[str, Any] = {
            "reqInfo": {"kind": "note", "data": inner_data, "guid": guid,
                        "etag": str(etag), "simpleNote": ""},
            "ctagNoteInfo": "", "startCursor": start_cursor or self._start_cursor,
            "traceId": _generate_traceid("03133"),
        }

        try:
            resp = self._request_with_retry(
                "POST", "https://cloud.huawei.com/notepad/note/update",
                headers=self._headers(), json=body, timeout=30, verify=False,
            )
            self._sync_cookies(resp)
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
        except requests.RequestException as e:
            return {"ok": False, "code": "-1", "msg": f"请求异常: {e}"}
        except json.JSONDecodeError as e:
            return {"ok": False, "code": "-2", "msg": f"响应解析失败: {e}"}

    def sync(
        self,
        ctag_note_info: str = "",
        ctag_task_info: str = "",
        start_cursor: Optional[str] = None,
    ) -> Result:
        """同步操作"""
        body: Dict[str, Any] = {
            "ctagNoteInfo": ctag_note_info, "ctagTaskInfo": ctag_task_info,
            "startCursor": start_cursor or self._start_cursor,
            "traceId": _generate_traceid("03131"),
        }
        data = self._post("https://cloud.huawei.com/notepad/sync", body, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        self._update_start_cursor(data)
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "同步成功" if code == "0" else f"失败({code})",
                "data": {"needSync": data.get("needSync", 0), "startCursor": data.get("startCursor", "")}}

    def get_task_detail(self, guid: str, ctag_task_info: str = "", start_cursor: Optional[str] = None) -> Result:
        """查询待办任务详情"""
        body: Dict[str, Any] = {
            "ctagTaskInfo": ctag_task_info,
            "startCursor": start_cursor or self._start_cursor, "guid": guid,
            "traceId": _generate_traceid("03131"),
        }
        data = self._post("https://cloud.huawei.com/notepad/task/query", body, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        self._update_start_cursor(data)
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "任务详情" if code == "0" else f"失败({code})",
                "data": data.get("rspInfo", {})}

    def get_graffiti_data(self, asset_id: str, record_id: str, version_id: str, kind: str = "newnote") -> Result:
        """获取涂鸦/手写笔记数据"""
        trace_id = _generate_traceid("03131")
        url = (f"https://cloud.huawei.com/proxyserver/getGraffitiData4V2"
               f"?traceId={trace_id}&assetId={asset_id}&recordId={record_id}"
               f"&versionId={version_id}&kind={kind}")
        data = self._get(url, "03131")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "涂鸦数据" if code == "0" else f"失败({code})", "data": data}

    def pre_process_file(
        self,
        need_to_sign_url: str = "",
        http_method: str = "GET",
        generate_sign_flag: bool = False,
    ) -> Result:
        """文件预签名"""
        body = {"needToSignUrl": need_to_sign_url, "httpMethod": http_method, "generateSignFlag": generate_sign_flag}
        data = self._post("https://cloud.huawei.com/proxyserver/driveFileProxy/preProcess", body, "03133")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "预签名成功" if code == "0" else f"失败({code})", "data": data}

    def refresh_cookies(self) -> Result:
        """刷新 cookies 并更新客户端状态"""
        data = self._post("https://cloud.huawei.com/html/queryCookieValuesByNames", {}, "25001")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        cookies = data.get("cookies", {})
        code = self._get_code(data)
        if code == "0" and cookies:
            self._csrf_token = cookies.get("CSRFToken", self._csrf_token)
            self._user_id = cookies.get("userId", self._user_id)
        return {"ok": code == "0", "code": code,
                "msg": f"刷新{len(cookies)}项" if code == "0" else f"失败({code})"}
