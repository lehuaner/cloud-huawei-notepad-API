"""华为云空间 · 会员/支付模块

基于抓包数据验证的 API 接口封装。

简化用法::

    # 获取用户等级信息
    grade = client.payment.get_user_grade_info()

    # 获取用户套餐
    package = client.payment.get_user_package()

    # 获取可用套餐列表
    packages = client.payment.get_available_grade_packages()

    # 获取可用优惠券
    vouchers = client.payment.get_ava_vouchers()

    # 获取客户端UI配置
    ui_config = client.payment.get_client_ui_config()
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import BaseModule, Result, _generate_traceid

logger = logging.getLogger("cloud-space-huawei.payment")


class PaymentModule(BaseModule):
    """华为云空间会员/支付

    通过 HuaweiCloudClient.payment 访问::

        client = HuaweiCloudClient.from_cookies(cookies)
        grade = client.payment.get_user_grade_info()
    """

    def get_user_grade_info(self) -> Result:
        """获取用户等级信息

        返回用户的会员等级、有效期等信息。

        Returns:
            包含 gradeCode, gradeState, validToTime 等字段
        """
        url = f"{self.BASE_URL}/payment/getUserGradeInfo"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "用户等级信息" if code == "0" else f"失败({code})",
                "data": {
                    "gradeCode": data.get("gradeCode", ""),
                    "gradeState": data.get("gradeState", 0),
                    "validToTime": data.get("validToTime", 0),
                    "hexCode": data.get("hexCode", ""),
                    "autoRenew": data.get("autoRenew", 0),
                    "gradeName": data.get("gradeName", ""),
                    "gradeDesc": data.get("gradeDesc", ""),
                    "originData": data,
                }}

    def get_user_package(self) -> Result:
        """获取用户套餐信息

        返回用户当前购买的云空间套餐详情。

        Returns:
            包含 packageId, packageName, packageSize 等字段
        """
        url = f"{self.BASE_URL}/payment/getUserPackage"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "用户套餐" if code == "0" else f"失败({code})",
                "data": data}

    def get_available_grade_packages(self) -> Result:
        """获取可购买的套餐列表

        返回所有可购买的云空间套餐，包含价格、容量等信息。

        Returns:
            包含 packageList 等字段
        """
        url = f"{self.BASE_URL}/payment/getAvailableGradePackages"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "可用套餐列表" if code == "0" else f"失败({code})",
                "data": data}

    def get_ava_vouchers(self) -> Result:
        """获取可用优惠券

        返回用户可用的优惠券列表。

        Returns:
            包含 voucherList 等字段
        """
        url = f"{self.BASE_URL}/payment/getAvaVouchers"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "可用优惠券" if code == "0" else f"失败({code})",
                "data": data}

    def get_client_ui_config(self) -> Result:
        """获取客户端 UI 配置

        返回支付相关的 UI 配置信息，如价格展示、购买按钮文案等。

        Returns:
            UI 配置信息
        """
        url = f"{self.BASE_URL}/payment/getClientUIConfig"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix="07102")
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = self._get_code(data)
        return {"ok": code == "0", "code": code,
                "msg": "客户端UI配置" if code == "0" else f"失败({code})",
                "data": data}
