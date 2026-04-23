"""华为云空间 · 查找设备模块 (骨架)"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import BaseModule, Result

logger = logging.getLogger("cloud-space-huawei.find_device")


class FindDeviceModule(BaseModule):
    """华为云查找设备

    通过 HuaweiCloudClient.find_device 访问。

    注意: 此模块为骨架，接口尚未实现，欢迎贡献 PR。
    """

    def get_device_list(self) -> Result:
        """获取设备列表 (未实现)"""
        raise NotImplementedError("查找设备接口尚未实现，欢迎贡献 PR")

    def locate_device(self, device_id: str) -> Result:
        """定位设备 (未实现)"""
        raise NotImplementedError("查找设备接口尚未实现，欢迎贡献 PR")

    def ring_device(self, device_id: str) -> Result:
        """响铃设备 (未实现)"""
        raise NotImplementedError("查找设备接口尚未实现，欢迎贡献 PR")
