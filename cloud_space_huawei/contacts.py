"""华为云空间 · 联系人模块 (骨架)"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import BaseModule, Result

logger = logging.getLogger("cloud-space-huawei.contacts")


class ContactsModule(BaseModule):
    """华为云联系人

    通过 HuaweiCloudClient.contacts 访问。

    注意: 此模块为骨架，接口尚未实现，欢迎贡献 PR。
    """

    def get_contacts(self) -> Result:
        """获取联系人列表 (未实现)"""
        raise NotImplementedError("联系人接口尚未实现，欢迎贡献 PR")

    def search_contacts(self, keyword: str) -> Result:
        """搜索联系人 (未实现)"""
        raise NotImplementedError("联系人接口尚未实现，欢迎贡献 PR")
