"""华为云空间 · 图库模块 (骨架)"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import BaseModule, Result

logger = logging.getLogger("cloud-space-huawei.gallery")


class GalleryModule(BaseModule):
    """华为云图库

    通过 HuaweiCloudClient.gallery 访问。

    注意: 此模块为骨架，接口尚未实现，欢迎贡献 PR。
    """

    def get_albums(self) -> Result:
        """获取相册列表 (未实现)"""
        raise NotImplementedError("图库接口尚未实现，欢迎贡献 PR")

    def get_photos(self, album_id: str = "") -> Result:
        """获取照片列表 (未实现)"""
        raise NotImplementedError("图库接口尚未实现，欢迎贡献 PR")

    def download_photo(self, photo_id: str) -> Result:
        """下载照片 (未实现)"""
        raise NotImplementedError("图库接口尚未实现，欢迎贡献 PR")
