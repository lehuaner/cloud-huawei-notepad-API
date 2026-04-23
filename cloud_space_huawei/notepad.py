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

    # ========== 备忘录 API ==========

    def get_tags(self, simplify: bool = True) -> Result:
        """获取标签列表

        Args:
            simplify: 是否精简返回数据，默认 True。精简时仅返回 etag、guid、
                     name、type、color 等关键字段。
        """
        data = self._post("https://cloud.huawei.com/notepad/notetag/query", {"index": 0}, "03135")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        rsp = data.get("rspInfo", {})

        def _parse_full_item(item: Dict[str, Any]) -> Dict[str, Any]:
            result: Dict[str, Any] = dict(item)
            if "data" in result and isinstance(result["data"], str):
                try:
                    content_obj = json.loads(result["data"])
                    if isinstance(content_obj, dict):
                        result["data"] = content_obj
                        if "content" in content_obj and isinstance(content_obj["content"], dict):
                            content_inner = content_obj["content"]
                            for field in ["data3", "data6"]:
                                if field in content_inner and isinstance(content_inner[field], str):
                                    try:
                                        content_inner[field] = json.loads(content_inner[field])
                                    except json.JSONDecodeError:
                                        pass
                except json.JSONDecodeError:
                    pass
            return result

        def _parse_simple_item(item: Dict[str, Any]) -> Dict[str, Any]:
            result: Dict[str, Any] = {"etag": item.get("etag", ""), "guid": item.get("guid", "")}
            if "data" in item and isinstance(item["data"], str):
                try:
                    content_obj = json.loads(item["data"])
                    if isinstance(content_obj, dict) and "content" in content_obj:
                        content_inner = content_obj["content"]
                        if isinstance(content_inner, dict):
                            if not result["guid"]:
                                result["guid"] = content_inner.get("guid", "")
                            result["name"] = content_inner.get("name", "")
                            result["type"] = content_inner.get("type", 0)
                            result["color"] = content_inner.get("color", "")
                            result["user_order"] = content_inner.get("user_order", 0)
                            result["create_time"] = content_inner.get("create_time", 0)
                            result["last_update_time"] = content_inner.get("last_update_time", 0)
                            result["version"] = content_inner.get("version", "")
                            result["delete_flag"] = content_inner.get("delete_flag", 0)

                            for field in ["data3", "data6"]:
                                if field in content_inner and isinstance(content_inner[field], str):
                                    try:
                                        content_inner[field] = json.loads(content_inner[field])
                                    except json.JSONDecodeError:
                                        pass

                            if isinstance(content_inner.get("data3"), dict):
                                result["folder_name"] = content_inner["data3"].get("mFolderName", "")
                                result["folder_uuid"] = content_inner["data3"].get("mFolderUuid", "")
                                result["tag_name"] = content_inner["data3"].get("mTagName", "")
                except json.JSONDecodeError:
                    pass
            return result

        if simplify:
            back_log_list = [_parse_simple_item(item) for item in rsp.get("backLoglist", [])]
            note_list = [_parse_simple_item(item) for item in rsp.get("noteList", [])]
        else:
            back_log_list = [_parse_full_item(item) for item in rsp.get("backLoglist", [])]
            note_list = [_parse_full_item(item) for item in rsp.get("noteList", [])]

        result_data = {"backLoglist": back_log_list, "noteList": note_list}
        total = len(back_log_list) + len(note_list)
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
            if resp.status_code == 402:
                return {"ok": False, "code": "402", "msg": "设备未认证(402)，请先完成设备信任认证"}
            if resp.status_code != 200:
                return {"ok": False, "code": str(resp.status_code), "msg": f"HTTP {resp.status_code}"}
            result = resp.json()
            # 检查响应体中的 402 code
            code = str(result.get("Result", {}).get("code", "-1"))
            if code == "402":
                return {"ok": False, "code": "402", "msg": "设备未认证(402)，请先完成设备信任认证"}
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
            if resp.status_code == 402:
                return {"ok": False, "code": "402", "msg": "设备未认证(402)，请先完成设备信任认证"}
            if resp.status_code != 200:
                return {"ok": False, "code": str(resp.status_code), "msg": f"HTTP {resp.status_code}"}
            if not resp.text:
                return {"ok": True, "code": "0", "msg": "更新成功", "data": {"guid": guid}}
            result = resp.json()
            # 检查响应体中的 402 code
            code = str(result.get("Result", {}).get("code", "-1"))
            if code == "402":
                return {"ok": False, "code": "402", "msg": "设备未认证(402)，请先完成设备信任认证"}
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


