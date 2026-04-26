"""华为云空间 · 云盘模块"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import time
from typing import Any, Dict, List, Optional, Union

from .base import (
    BaseModule,
    LONG_TIMEOUT,
    MEDIUM_TIMEOUT,
    Result,
    TRACE_CREATE_FILE,
    TRACE_DELETE_FILE,
    TRACE_DOWNLOAD_FILE,
    TRACE_MOVE_FILE,
    TRACE_NOTIFY_SYNC,
    TRACE_QUERY_FILE,
    TRACE_RENAME_FILE,
    TRACE_RESTORE_FILE,
    TRACE_UPLOAD_FILE,
    _generate_traceid,
)

logger = logging.getLogger("cloud-space-huawei.drive")


class DriveModule(BaseModule):
    """华为云盘

    通过 HuaweiCloudClient.drive 访问::

        client = HuaweiCloudClient.from_cookies(cookies)
        files = client.drive.list_files()
    """

    # ========== 云盘文件 API ==========

    def list_files(
        self,
        folder_id: str = "",
        order: str = "editedTime desc",
        cursor: str = "",
        folder_flag: int = 3,
    ) -> Result:
        """列出云盘文件

        Args:
            folder_id: 文件夹ID，默认为根目录 "root"
            order: 排序方式，默认 "editedTime desc"
            cursor: 分页游标，用于翻页
            folder_flag: 显示模式，3=所有，1=只显示文件夹，2=只显示文件

        Returns:
            文件列表，包含以下字段：
            - files: 文件列表
            - nextCursor: 下一页游标
            - serverTime: 服务器时间
        """
        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_QUERY_FILE),
            "id": folder_id or "root",
            "order": order,
            "cursor": cursor,
            "folderFlag": folder_flag,
        }
        data = self._post("https://cloud.huawei.com/syncDrive/queryDriveFile", body, TRACE_QUERY_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        files = data.get("files", [])
        next_cursor = data.get("nextCursor", "")
        total = len(files)
        return {
            "ok": code == "0",
            "code": code,
            "msg": f"{total}个文件" if code == "0" else f"失败({code})",
            "data": {
                "files": files,
                "nextCursor": next_cursor,
                "serverTime": data.get("serverTime", 0),
            },
        }

    def create_folder(self, name: str, parent_id: str = "root") -> Result:
        """创建文件夹

        Args:
            name: 文件夹名称
            parent_id: 父文件夹ID，默认为根目录 "root"

        Returns:
            创建的文件夹信息
        """
        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_CREATE_FILE),
            "files": {
                "type": "application/vnd.huawei-apps.folder",
                "name": name,
            },
            "parentFolder": parent_id,
            "showInRecentListFlag": True,
        }
        data = self._post("https://cloud.huawei.com/syncDrive/mkDriveFile", body, TRACE_CREATE_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        file_data = data.get("data", {})
        return {
            "ok": code == "0",
            "code": code,
            "msg": "创建成功" if code == "0" else f"失败({code})",
            "data": file_data,
        }

    def delete_files(
        self,
        file_ids: List[Dict[str, Any]],
        src_path: str = "",
        del_type: int = 0,
    ) -> Result:
        """删除文件（移入回收站）

        Args:
            file_ids: 文件ID列表，每项包含 fieldId 和 baseVersion
                     如: [{"fieldId": "xxx", "baseVersion": 1}]
            src_path: 源路径（URL编码）
            del_type: 删除类型，0=移入回收站

        Returns:
            删除结果
        """
        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_DELETE_FILE),
            "delType": del_type,
            "srcPath": src_path,
            "fileList": file_ids,
        }
        data = self._post("https://cloud.huawei.com/syncDrive/delDriveFile", body, TRACE_DELETE_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        success_list = data.get("successList", [])
        fail_list = data.get("failList", [])
        return {
            "ok": code == "0",
            "code": code,
            "msg": f"删除{len(success_list)}个" if code == "0" else f"失败({code})",
            "data": {
                "successList": success_list,
                "failList": fail_list,
            },
        }

    def restore_files(
        self,
        file_ids: List[str],
        cursor: str = "",
    ) -> Result:
        """恢复回收站文件

        Args:
            file_ids: 要恢复的文件ID列表
            cursor: 分页游标

        Returns:
            恢复结果
        """
        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_RESTORE_FILE),
            "fileIdList": file_ids,
            "cursor": cursor,
        }
        data = self._post("https://cloud.huawei.com/syncDrive/restoreDriveFile", body, TRACE_RESTORE_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        success_list = data.get("successList", [])
        new_success_list = data.get("newSuccessList", [])
        fail_list = data.get("failList", [])
        return {
            "ok": code == "0",
            "code": code,
            "msg": f"恢复{len(success_list)}个" if code == "0" else f"失败({code})",
            "data": {
                "successList": success_list,
                "newSuccessList": new_success_list,
                "failList": fail_list,
            },
        }

    def move_files(
        self,
        file_ids: List[str],
        dest_folder_id: str,
    ) -> Result:
        """移动文件到指定文件夹

        Args:
            file_ids: 要移动的文件ID列表
            dest_folder_id: 目标文件夹ID

        Returns:
            移动结果
        """
        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_MOVE_FILE),
            "fileIdList": file_ids,
            "destId": dest_folder_id,
        }
        data = self._post("https://cloud.huawei.com/syncDrive/moveDriveFile", body, TRACE_MOVE_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        success_list = data.get("successList", [])
        fail_list = data.get("failList", [])
        return {
            "ok": code == "0",
            "code": code,
            "msg": f"移动{len(success_list)}个" if code == "0" else f"失败({code})",
            "data": {
                "successList": success_list,
                "failList": fail_list,
            },
        }

    def rename_file(
        self,
        file_id: str,
        new_name: str,
    ) -> Result:
        """重命名文件

        Args:
            file_id: 文件ID
            new_name: 新名称（URL编码后的名称会自动处理）

        Returns:
            重命名后的文件信息
        """
        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_RENAME_FILE),
            "fileId": file_id,
            "name": new_name,
        }
        data = self._post("https://cloud.huawei.com/syncDrive/renameDriveFile", body, TRACE_RENAME_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        file_data = data.get("file", {})
        return {
            "ok": code == "0",
            "code": code,
            "msg": "重命名成功" if code == "0" else f"失败({code})",
            "data": file_data,
        }

    def get_file_detail(self, file_id: str) -> Result:
        """获取文件详情

        Args:
            file_id: 文件ID

        Returns:
            文件详细信息
        """
        # 从根目录开始查询文件列表
        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_QUERY_FILE),
            "id": "root",
            "order": "editedTime desc",
            "cursor": "",
            "folderFlag": 3,
        }
        data = self._post("https://cloud.huawei.com/syncDrive/queryDriveFile", body, TRACE_QUERY_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}

        files = data.get("files", [])
        for f in files:
            if f.get("id") == file_id:
                return {
                    "ok": True,
                    "code": "0",
                    "msg": "文件详情",
                    "data": f,
                }

        # 如果在根目录找不到，递归搜索子目录
        for f in files:
            if f.get("mimeType") == "application/vnd.huawei-apps.folder":
                sub_result = self._search_in_folder(file_id, f.get("id", ""))
                if sub_result.get("ok"):
                    return sub_result

        return {
            "ok": False,
            "code": "404",
            "msg": "文件未找到",
            "data": {},
        }

    def _search_in_folder(self, file_id: str, folder_id: str, max_depth: int = 5) -> Result:
        """在指定文件夹中递归搜索文件"""
        if max_depth <= 0:
            return {"ok": False, "code": "404", "msg": "搜索深度超限", "data": {}}

        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_QUERY_FILE),
            "id": folder_id,
            "order": "editedTime desc",
            "cursor": "",
            "folderFlag": 3,
        }
        data = self._post("https://cloud.huawei.com/syncDrive/queryDriveFile", body, TRACE_QUERY_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}

        files = data.get("files", [])
        for f in files:
            if f.get("id") == file_id:
                return {
                    "ok": True,
                    "code": "0",
                    "msg": "文件详情",
                    "data": f,
                }
            # 如果是文件夹，继续递归搜索
            if f.get("mimeType") == "application/vnd.huawei-apps.folder":
                sub_result = self._search_in_folder(file_id, f.get("id", ""), max_depth - 1)
                if sub_result.get("ok"):
                    return sub_result

        return {"ok": False, "code": "404", "msg": "文件未找到", "data": {}}

    # ========== 文件上传 API ==========

    def pre_upload_process(
        self,
        need_to_sign_url: str = "/upload/drive/v1/files?uploadType=resume&fields=*",
        http_method: str = "POST",
    ) -> Result:
        """上传预处理 - 获取签名

        Args:
            need_to_sign_url: 需要签名的URL路径
            http_method: HTTP方法

        Returns:
            签名信息，包含 sign 和 requestTimeStamp
        """
        body: Dict[str, Any] = {
            "needToSignUrl": need_to_sign_url,
            "httpMethod": http_method,
            "generateSignFlag": True,
        }
        data = self._post("https://cloud.huawei.com/proxyserver/driveFileProxy/preProcess", body, TRACE_UPLOAD_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {
            "ok": code == "0",
            "code": code,
            "msg": "预处理成功" if code == "0" else f"失败({code})",
            "data": {
                "sign": data.get("sign", ""),
                "requestTimeStamp": data.get("requestTimeStamp", ""),
            },
        }

    def upload_file(
        self,
        file_path: str,
        parent_folder_id: str = "",
        chunk_size: int = 5 * 1024 * 1024,
        show_in_recent: bool = True,
    ) -> Result:
        """上传文件到云盘（完整流程）

        流程：
        1. pre_upload_process - 获取上传签名
        2. POST 文件内容到上传接口
        3. 通知同步

        Args:
            file_path: 本地文件路径
            parent_folder_id: 父文件夹ID，默认为根目录
            chunk_size: 分片大小（仅对 resume 模式有效）
            show_in_recent: 是否显示在最近列表

        Returns:
            上传结果
        """
        if not os.path.exists(file_path):
            return {"ok": False, "code": "404", "msg": f"文件不存在: {file_path}"}

        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        # 获取文件sha256（分块读取避免大文件 OOM）
        try:
            sha256 = self._compute_sha256(file_path)
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"读取文件失败: {e}"}

        # 读取文件内容用于上传（multipart 构造需要完整字节）
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except OSError as e:
            return {"ok": False, "code": "-1", "msg": f"读取文件失败: {e}"}

        # 1. 预处理获取签名
        # 注意：need_to_sign_url 必须与实际请求的路径一致
        # 根据抓包数据，正确的 URL 路径是 /upload/drive/v1/files
        need_sign_url = "/upload/drive/v1/files?uploadType=content&fields=*"
        pre_result = self.pre_upload_process(
            need_to_sign_url=need_sign_url,
            http_method="POST"
        )
        if not pre_result.get("ok"):
            return {"ok": False, "code": pre_result.get("code", "-1"), "msg": f"[步骤1-预处理] {pre_result.get('msg')}"}

        sign = pre_result["data"].get("sign", "")
        time_stamp = pre_result["data"].get("requestTimeStamp", str(int(time.time() * 1000)))

        # 2. 直接上传文件（content 模式）
        # 使用 multipart/form-data 格式（根据抓包数据分析）
        import urllib.parse

        # 构建 x-hw-properties header
        parent_folder = parent_folder_id if parent_folder_id else "root"
        hw_properties = urllib.parse.urlencode({
            "fileName": file_name,
            "mimeType": mime_type,
            "parentFolder": parent_folder,
            "attributes": '{"batchOperTime":"0"}'
        })
        
        # 生成 multipart boundary
        boundary = "----WebKitFormBoundary" + hashlib.md5(
            f"{time.time()}{file_name}".encode()
        ).hexdigest()[:16]
        
        # 构建 multipart body
        body_parts = []
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode()
        )
        body_parts.append(f"Content-Type: {mime_type}\r\n".encode())
        body_parts.append(b"\r\n")
        body_parts.append(file_bytes)
        body_parts.append(f"\r\n--{boundary}--\r\n".encode())
        multipart_body = b"".join(body_parts)
        
        url = f"https://cloud.huawei.com/upload/drive/v1/files?uploadType=content&fields=*&timeStamp={time_stamp}"

        headers = {
            **self._headers(),
            "x-hw-trace-id": _generate_traceid(TRACE_UPLOAD_FILE),
            "x-hw-signature": sign,
            "x-hw-properties": hw_properties,
            "x-hw-device-type": "7",
            "content-type": f"multipart/form-data; boundary={boundary}",
            "accept": "application/json, text/plain, */*",
        }

        try:
            resp = self._request_with_retry(
                "POST", url, headers=headers, data=multipart_body, timeout=MEDIUM_TIMEOUT, verify=False,
            )
            self._sync_cookies(resp)
            logger.debug("上传响应状态码: %s", resp.status_code)
            if resp.status_code != 200:
                logger.warning("上传失败，状态码: %s, 响应: %s", resp.status_code, resp.text[:500])
                return {"ok": False, "code": str(resp.status_code), "msg": f"[步骤2-上传] HTTP {resp.status_code}, 响应: {resp.text[:200]}"}
            data = resp.json()
            logger.debug("上传响应数据: %s", data)
            
            # 检查错误响应
            if "error" in data:
                return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
            
            # 上传成功时，响应包含 category 字段
            if data.get("category") == "drive#file" or data.get("id"):
                # 3. 通知同步
                self._notify_sync()
                file_id = data.get("id", "")
                # 使用响应中的实际文件名（可能与上传时不同）
                actual_filename = data.get("fileName", file_name)
                return {
                    "ok": True,
                    "code": "0",
                    "msg": "上传成功",
                    "data": {
                        "id": file_id,
                        "fileName": actual_filename,
                        "size": data.get("size", file_size),
                        "sha256": data.get("sha256", sha256),
                    },
                }
            
            # 其他情况
            code = self._get_code(data)
            return {"ok": False, "code": code, "msg": f"[步骤2-上传] 失败({code}), 响应: {data}"}
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"[步骤2-上传] 异常: {e}"}

    def _notify_sync(self) -> Result:
        """通知同步"""
        body: Dict[str, Any] = {
            "traceId": _generate_traceid(TRACE_NOTIFY_SYNC),
        }
        data = self._post("https://cloud.huawei.com/syncDrive/notifySyncDrive", body, TRACE_NOTIFY_SYNC)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {
            "ok": code == "0",
            "code": code,
            "msg": "同步通知成功" if code == "0" else f"失败({code})",
        }

    # ========== 文件下载 API ==========

    def pre_download_process(self, file_id: str) -> Result:
        """下载预处理 - 获取下载URL

        Args:
            file_id: 文件ID

        Returns:
            下载URL信息
        """
        body: Dict[str, Any] = {
            "needToSignUrl": f"/drive/v1/files/{file_id}?form=content",
            "httpMethod": "GET",
            "generateSignFlag": True,
        }
        data = self._post("https://cloud.huawei.com/proxyserver/driveFileProxy/preProcess", body, TRACE_DOWNLOAD_FILE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {
            "ok": code == "0",
            "code": code,
            "msg": "预处理成功" if code == "0" else f"失败({code})",
            "data": data,
        }

    def get_download_url(self, file_id: str) -> Result:
        """获取文件下载URL

        Args:
            file_id: 文件ID

        Returns:
            下载URL信息，包含 downloadUrl 和 sign
        """
        # 使用 pre_download_process 获取带签名的下载URL
        pre_result = self.pre_download_process(file_id)
        if pre_result.get("ok"):
            pre_data = pre_result.get("data", {})
            return {
                "ok": True,
                "code": "0",
                "msg": "获取下载URL成功",
                "data": {
                    "downloadUrl": pre_data.get("downloadUrl", ""),
                    "sign": pre_data.get("sign", ""),
                    "requestTimeStamp": pre_data.get("requestTimeStamp", ""),
                    "fileId": file_id,
                },
            }
        return {"ok": False, "code": "-1", "msg": f"获取下载URL失败: {pre_result.get('msg')}"}


    def download_file(
        self,
        file_id: str,
        save_path: str = "",
    ) -> Result:
        """下载云盘文件

        Args:
            file_id: 文件ID
            save_path: 保存路径，为空则返回二进制内容

        Returns:
            下载结果
        """
        # 1. 获取文件信息
        detail_result = self.get_file_detail(file_id)
        if not detail_result.get("ok"):
            return detail_result

        file_info = detail_result.get("data", {})
        file_name = file_info.get("fileName", "")
        content_link = file_info.get("contentDownloadLink", "")

        if not content_link:
            # 尝试获取下载链接
            download_result = self.get_download_url(file_id)
            if download_result.get("ok"):
                # get_download_url 返回 downloadUrl 或 sign
                dl_data = download_result.get("data", {})
                content_link = dl_data.get("downloadUrl", "")
                # 如果没有 downloadUrl 但有 sign，可以用带签名的URL下载
                if not content_link and dl_data.get("sign"):
                    content_link = f"https://cloud.huawei.com/drive/v1/files/{file_id}?form=content"

        if not content_link:
            return {"ok": False, "code": "-1", "msg": "无法获取下载链接"}

        # 2. 下载文件
        try:
            resp = self._request_with_retry(
                "GET", content_link, headers=self._headers(), timeout=LONG_TIMEOUT, verify=False,
            )
            self._sync_cookies(resp)

            if resp.status_code == 200:
                content = resp.content

                # 3. 保存文件
                if not save_path:
                    save_path = file_name

                os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(content)

                return {
                    "ok": True,
                    "code": "0",
                    "msg": "下载成功",
                    "data": {
                        "path": save_path,
                        "size": len(content),
                        "fileName": file_name,
                    },
                }

            return {"ok": False, "code": str(resp.status_code), "msg": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"下载异常: {e}"}

    def get_thumbnail_url(self, file_id: str) -> Result:
        """获取文件缩略图URL

        Args:
            file_id: 文件ID

        Returns:
            缩略图URL
        """
        detail_result = self.get_file_detail(file_id)
        if not detail_result.get("ok"):
            return detail_result

        file_info = detail_result.get("data", {})
        thumbnail_url = file_info.get("thumbnailDownloadLink", "")
        small_thumbnail_url = file_info.get("smallThumbnailDownloadLink", "")

        return {
            "ok": True,
            "code": "0",
            "msg": "获取成功",
            "data": {
                "thumbnailUrl": thumbnail_url,
                "smallThumbnailUrl": small_thumbnail_url,
            },
        }

    def download_thumbnail(self, file_id: str, save_path: str = "") -> Result:
        """下载文件缩略图

        Args:
            file_id: 文件ID
            save_path: 保存路径，为空则返回二进制内容

        Returns:
            下载结果
        """
        url_result = self.get_thumbnail_url(file_id)
        if not url_result.get("ok"):
            return url_result

        thumbnail_url = url_result.get("data", {}).get("smallThumbnailUrl") or url_result.get(
            "data", {}
        ).get("thumbnailUrl", "")

        if not thumbnail_url:
            return {"ok": False, "code": "-1", "msg": "无缩略图"}

        try:
            resp = self._request_with_retry(
                "GET", thumbnail_url, headers=self._headers(), timeout=60, verify=False,
            )
            self._sync_cookies(resp)

            if resp.status_code == 200:
                content = resp.content

                if not save_path:
                    return {
                        "ok": True,
                        "code": "0",
                        "msg": "下载成功",
                        "data": {"content": content, "contentType": resp.headers.get("Content-Type", "")},
                    }

                os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(content)

                return {
                    "ok": True,
                    "code": "0",
                    "msg": "下载成功",
                    "data": {"path": save_path, "size": len(content)},
                }

            return {"ok": False, "code": str(resp.status_code), "msg": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"下载异常: {e}"}

    # ========== 批量操作 API ==========

    def batch_delete(self, file_ids: List[str], versions: List[int] = None) -> Result:
        """批量删除文件

        Args:
            file_ids: 文件ID列表
            versions: 对应的版本列表，不提供则默认1

        Returns:
            删除结果
        """
        if versions is None:
            versions = [1] * len(file_ids)

        file_list = [
            {"fieldId": fid, "baseVersion": ver}
            for fid, ver in zip(file_ids, versions)
        ]
        return self.delete_files(file_list)

    def batch_move(
        self,
        file_ids: List[str],
        dest_folder_id: str,
    ) -> Result:
        """批量移动文件

        Args:
            file_ids: 文件ID列表
            dest_folder_id: 目标文件夹ID

        Returns:
            移动结果
        """
        return self.move_files(file_ids, dest_folder_id)

    def batch_restore(self, file_ids: List[str]) -> Result:
        """批量恢复文件

        Args:
            file_ids: 文件ID列表

        Returns:
            恢复结果
        """
        return self.restore_files(file_ids)

    # ---------- 工具方法 ----------

    @staticmethod
    def _compute_sha256(file_path: str, chunk_size: int = 8192) -> str:
        """分块计算文件 SHA256（避免大文件 OOM）"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    # ---------- 批量操作 API ----------

    def batch_rename(self, rename_info: List[Dict[str, Any]]) -> Result:
        """批量重命名文件

        Args:
            rename_info: 重命名信息列表，如 [{"fileId": "xxx", "newName": "new.txt"}]

        Returns:
            重命名结果
        """
        success_list = []
        fail_list = []

        for info in rename_info:
            file_id = info.get("fileId", "")
            new_name = info.get("newName", "")
            if not file_id or not new_name:
                continue
            result = self.rename_file(file_id, new_name)
            if result.get("ok"):
                success_list.append({"fileId": file_id, "file": result.get("data", {})})
            else:
                fail_list.append({"fileId": file_id, "reason": result.get("msg", "")})

        return {
            "ok": len(fail_list) == 0,
            "code": "0" if len(fail_list) == 0 else "partial",
            "msg": f"成功{len(success_list)}个，失败{len(fail_list)}个",
            "data": {
                "successList": success_list,
                "failList": fail_list,
            },
        }
