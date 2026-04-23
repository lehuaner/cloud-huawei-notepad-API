"""华为云空间 · 云盘模块 (骨架)"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import BaseModule, Result

logger = logging.getLogger("cloud-space-huawei.drive")


class DriveModule(BaseModule):
    """华为云盘

    通过 HuaweiCloudClient.drive 访问。

    注意: 此模块为骨架，接口尚未实现，欢迎贡献 PR。
    """

    def list_files(self, parent_id: str = "") -> Result:
        """列出文件 (未实现)"""
        raise NotImplementedError("云盘接口尚未实现，欢迎贡献 PR")

    def upload_file(self, file_path: str, parent_id: str = "") -> Result:
        """上传文件 (未实现)"""
        raise NotImplementedError("云盘接口尚未实现，欢迎贡献 PR")

    def download_file(self, file_id: str, save_path: str = "") -> Result:
        """下载文件 (未实现)"""
        raise NotImplementedError("云盘接口尚未实现，欢迎贡献 PR")

    def create_folder(self, name: str, parent_id: str = "") -> Result:
        """创建文件夹 (未实现)"""
        raise NotImplementedError("云盘接口尚未实现，欢迎贡献 PR")

    def delete_file(self, file_id: str) -> Result:
        """删除文件 (未实现)"""
        raise NotImplementedError("云盘接口尚未实现，欢迎贡献 PR")
