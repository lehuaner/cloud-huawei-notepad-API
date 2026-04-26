"""华为云空间 · 版本管理模块

基于抓包数据验证的 API 接口封装。

注意：revisions 系列接口的响应格式与其他模块不同，使用
``result.resultCode`` 而非顶层 ``code`` 字段。

简化用法::

    # 查询版本修订权限
    right = client.revisions.query_revision_right()

    # 获取文件版本列表 (需要 service)
    revisions = client.revisions.get_revisions(service="addressbook")

    # 获取版本恢复状态 (需要 service + revertId)
    status = client.revisions.get_retrieve_status(service="addressbook", revert_id="xxx")

    # 恢复文件版本
    result = client.revisions.retrieve(service="addressbook", revision_id="xxx")

    # 更新恢复状态
    client.revisions.update_retrieve_status(
        service="addressbook", revision_id="xxx",
        create_time=1777221351986, revert_id="xxx"
    )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseModule, Result

logger = logging.getLogger("cloud-space-huawei.revisions")


class RevisionsModule(BaseModule):
    """华为云空间版本管理

    通过 HuaweiCloudClient.revisions 访问::

        client = HuaweiCloudClient.from_cookies(cookies)
        right = client.revisions.query_revision_right()
    """

    @staticmethod
    def _get_rev_code(data: Dict[str, Any]) -> str:
        """从 revisions 专用响应格式提取结果码

        revisions 接口返回格式为 ``{"result": {"resultCode": "0", ...}}``
        而非通用的 ``{"code": "0"}``。
        """
        result_obj = data.get("result", {})
        if isinstance(result_obj, dict):
            return str(result_obj.get("resultCode", ""))
        return ""

    @staticmethod
    def _is_rev_success(data: Dict[str, Any]) -> bool:
        """判断 revisions 接口是否成功"""
        return RevisionsModule._get_rev_code(data) == "0"

    def query_revision_right(self) -> Result:
        """查询版本修订权限

        返回用户是否具有文件版本管理权限。

        Returns:
            包含 rightFlag 等字段 (1=有权限, 0=无权限)
        """
        url = f"{self.BASE_URL}/revisions/queryRevisionRight"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_rev_code(data)
        ok = code == "0"
        return {"ok": ok, "code": code,
                "msg": "版本修订权限" if ok else f"失败({code})",
                "data": {
                    "rightFlag": data.get("rightFlag", 0),
                    "originData": data,
                }}

    def get_revisions(
        self,
        service: str = "addressbook",
    ) -> Result:
        """获取文件版本列表

        返回指定服务的版本历史记录。

        Args:
            service: 服务名（默认 "addressbook"，即通讯录）

        Returns:
            包含 dataList 等字段，每项含 id、createTime、byteSize、channel、
            changeLog、itemCount 等
        """
        url = f"{self.BASE_URL}/revisions/getRevisions"
        body: Dict[str, Any] = {
            "service": service,
        }
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_rev_code(data)
        ok = code == "0"
        result_desc = data.get("result", {}).get("resultDesc", "")
        return {"ok": ok, "code": code,
                "msg": "版本列表" if ok else f"失败({code}: {result_desc})",
                "data": data}

    def get_retrieve_status(
        self,
        service: str = "addressbook",
        revert_id: str = "",
    ) -> Result:
        """获取版本恢复状态

        查询文件版本恢复操作的当前状态。

        Args:
            service: 服务名（默认 "addressbook"）
            revert_id: 恢复操作ID（由 retrieve() 返回的 status.revertId）

        Returns:
            包含 status 等字段（status.status: 0=进行中, 1=完成）
        """
        url = f"{self.BASE_URL}/revisions/getRetrieveStatus"
        body: Dict[str, Any] = {
            "service": service,
        }
        if revert_id:
            body["revertId"] = revert_id
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_rev_code(data)
        ok = code == "0"
        result_desc = data.get("result", {}).get("resultDesc", "")
        return {"ok": ok, "code": code,
                "msg": "恢复状态" if ok else f"失败({code}: {result_desc})",
                "data": data}

    def retrieve(
        self,
        service: str = "addressbook",
        revision_id: str = "",
    ) -> Result:
        """恢复文件版本

        将文件恢复到指定版本。

        Args:
            service: 服务名（默认 "addressbook"）
            revision_id: 版本ID（必填，从 getRevisions() 返回的 dataList 中获取 id）

        Returns:
            恢复操作结果，包含 status（含 revertId、status、createTime 等）

        Note:
            revision_id 为必填参数，可从 ``get_revisions()`` 返回的 dataList 中获取。
        """
        url = f"{self.BASE_URL}/revisions/retrieve"
        body: Dict[str, Any] = {
            "service": service,
        }
        if revision_id:
            body["revisionId"] = revision_id
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_rev_code(data)
        ok = code == "0"
        return {"ok": ok, "code": code,
                "msg": "恢复请求已发送" if ok else f"失败({code})",
                "data": data}

    def update_retrieve_status(
        self,
        service: str = "addressbook",
        revision_id: str = "",
        create_time: int = 0,
        revert_id: str = "",
    ) -> Result:
        """更新恢复状态

        确认文件版本恢复操作已完成。

        Args:
            service: 服务名（默认 "addressbook"）
            revision_id: 版本ID（从 retrieve() 的 status.id 获取）
            create_time: 恢复操作创建时间（从 retrieve() 的 status.createTime 获取）
            revert_id: 恢复操作ID（从 retrieve() 的 status.revertId 获取）

        Returns:
            更新操作结果
        """
        url = f"{self.BASE_URL}/revisions/updateRetrieveStatus"
        body: Dict[str, Any] = {
            "service": service,
        }
        if revision_id:
            body["revisionId"] = revision_id
        if create_time:
            body["createTime"] = create_time
        if revert_id:
            body["revertId"] = revert_id
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_rev_code(data)
        ok = code == "0"
        return {"ok": ok, "code": code,
                "msg": "状态已更新" if ok else f"失败({code})",
                "data": data}
