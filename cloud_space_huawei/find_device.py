"""华为云空间 · 查找设备模块

基于抓包数据验证的 API 接口封装。

简化用法::

    # 获取查找设备首页数据
    home_data = client.find_device.get_home_data()

    # 获取设备列表
    devices = client.find_device.get_device_list()

    # 定位设备
    client.find_device.locate(device_id="xxx", device_type=9)

    # 查询定位结果
    result = client.find_device.query_locate_result(device_id="xxx", device_type=9)

    # 播放铃声
    client.find_device.play_bell(device_id="xxx", device_type=9)

    # 开启丢失模式
    client.find_device.start_lost_mode(
        device_id="xxx",
        device_type=9,
        message="这是我的设备，请归还",
        phone_num="+86138****8888"
    )

    # 关闭丢失模式
    client.find_device.stop_lost_mode(device_id="xxx", device_type=9)

    # 查询轨迹
    tracks = client.find_device.query_tracks(device_id="xxx", device_type=9)

    # 查询命令结果
    result = client.find_device.query_cmd_result(device_id="xxx", device_type=9,
                                                  cmds=["clear", "lockScreen"])

    # 查询国际区号
    codes = client.find_device.query_country_calling_code()

    # 上报地图健康状态
    client.find_device.report_map_health()
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseModule, Result, _generate_traceid

logger = logging.getLogger("cloud-space-huawei.find_device")

# ============================================================
# 常量
# ============================================================

FIND_DEVICE_URL = "https://cloud.huawei.com/findDevice"

# Trace ID 前缀
TRACE_GET_HOME = "00001"      # 获取首页数据
TRACE_DEVICE_LIST = "01100"   # 获取设备列表
TRACE_LOCATE = "01001"        # 定位
TRACE_BELL = "01007"          # 响铃
TRACE_LOST_MODE = "01004"     # 丢失模式
TRACE_TRACKS = "01001"        # 轨迹查询
TRACE_PATTERN = "01004"        # 锁定模式
TRACE_CMD_RESULT = "01001"    # 命令结果查询
TRACE_MAP_HEALTH = "01001"    # 地图健康上报

# 设备类型
DEVICE_TYPE_PHONE = 9         # 手机
DEVICE_TYPE_PAD = 2           # 平板
DEVICE_TYPE_WATCH = 1          # 手表
DEVICE_TYPE_TAG = -1          # 标签/配件

# 设备类型名称映射（仅用于 deviceType 为 -1 或无 deviceCategory 时）
DEVICE_TYPE_NAMES = {
    1: "手表",
    0: "未知",
    -1: "配件",
}


class FindDeviceModule(BaseModule):
    """华为云空间查找设备

    通过 HuaweiCloudClient.find_device 访问::

        client = HuaweiCloudClient.from_cookies(cookies)
        devices = client.find_device.get_device_list()
    """

    # ---------- 基础信息 ----------

    def get_home_data(self) -> Result:
        """获取查找设备首页数据

        返回配置信息如地图 API URL、超时设置、用户信息等。

        Returns:
            包含 amapUrl, hwMapKey, userName, accountName 等配置
        """
        url = f"{FIND_DEVICE_URL}/getHomeData"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix=TRACE_GET_HOME)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        if code != "0":
            return {"ok": False, "code": code,
                    "msg": data.get("info", f"失败({code})"), "data": {}}

        # 提取关键配置
        result_data = {
            "userName": data.get("userName", ""),
            "accountName": data.get("accountName", ""),
            "userEmail": data.get("userEmail", ""),
            "secretPhone": data.get("secretPhone", ""),
            "countryCode": data.get("countryCode", ""),
            "lang": data.get("lang", ""),
            "hwMapKey": data.get("hwMapKey", ""),
            "hwMapRestApiUrl": data.get("hwMapRestApiUrl", ""),
            "hwMapStaticUrl": data.get("hwMapStaticUrl", ""),
            "amapUrl": data.get("amapUrl", ""),
            "amapWebapiUrl": data.get("amapWebapiUrl", ""),
            "serverTime": data.get("serverTime", 0),
            "bellTimeoutForMain": data.get("bellTimeoutForMain", 35),
            "bellTimeoutForMainOffline": data.get("bellTimeoutForMainOffline", 150),
            "locateUpdateTime": data.get("locateUpdateTime", 60),
            "enableShare": data.get("enableShare", 0),
            "enableOfflineLocation": data.get("enableOfflineLocation", 0),
        }
        return {"ok": True, "code": code,
                "msg": "首页数据", "data": result_data}

    def get_user_info(self) -> Result:
        """获取用户信息（简化版）"""
        url = f"{FIND_DEVICE_URL}/getInfos"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix=TRACE_DEVICE_LIST)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        result_data = {
            "userImg": data.get("userImg", ""),
            "userName": data.get("userName", ""),
        }
        return {"ok": code == "0", "code": code,
                "msg": "用户信息" if code == "0" else f"失败({code})", "data": result_data}

    def get_share_grant_info(self) -> Result:
        """获取分享授权信息"""
        url = f"{FIND_DEVICE_URL}/getShareGrantInfo"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix=TRACE_DEVICE_LIST)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "分享授权信息" if code == "0" else f"失败({code})",
                "data": {
                    "shareGrantInfoList": data.get("shareGrantInfoList", []),
                    "serverTime": data.get("serverTime", 0),
                }}

    # ---------- 设备列表 ----------

    def get_device_list(self, tab_location: int = 2) -> Result:
        """获取设备列表

        Args:
            tab_location: 选项卡位置，2=全部设备

        Returns:
            包含 deviceList，每项含 deviceId, deviceAliasName, deviceType,
            deviceCategory, capability, onlineStatus 等
        """
        url = f"{FIND_DEVICE_URL}/getMobileDeviceList"
        body: Dict[str, Any] = {
            "tabLocation": tab_location,
            "portalType": 0,
        }
        data = self._post(url, body, trace_prefix=TRACE_DEVICE_LIST)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        if code != "0":
            return {"ok": False, "code": code,
                    "msg": data.get("info", f"失败({code})"), "data": {}}

        device_list = data.get("deviceList", [])
        # 解析每个设备的关键信息
        parsed_devices = [self._parse_device(d) for d in device_list]

        return {"ok": True, "code": code,
                "msg": f"{len(device_list)}个设备", "data": {"deviceList": parsed_devices}}

    def _get_device_type_name(self, device: Dict[str, Any]) -> str:
        """根据 deviceCategory 和 deviceType 获取设备类型名称
        
        华为云空间 API 的 deviceType 值不固定，需要结合 deviceCategory 来判断：
        - deviceCategory: "pad" -> 平板
        - deviceCategory: "phone" -> 手机
        - deviceType: -1 或无 deviceCategory -> 配件
        - deviceType: 1 -> 手表
        """
        category = device.get("deviceCategory", "")
        device_type = device.get("deviceType", 0)
        
        if category == "pad":
            return "平板"
        elif category == "phone":
            return "手机"
        elif device_type == 1:
            return "手表"
        elif device_type == -1 or not category:
            return "配件"
        else:
            return "未知"

    def _parse_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """解析设备信息"""
        result = {
            "deviceId": device.get("deviceId", ""),
            "deviceAliasName": device.get("deviceAliasName", ""),
            "deviceType": device.get("deviceType", 0),
            "deviceTypeName": self._get_device_type_name(device),
            "deviceCategory": device.get("deviceCategory", ""),
            "deviceSn": device.get("deviceSn", ""),
            "packageName": device.get("packageName", ""),
            "appVersion": device.get("appVersion", ""),
            "romVersion": device.get("romVersion", ""),
            "capability": device.get("capability", []),
            "offlineStatus": device.get("offlineStatus", 0),
            "offlineMKVersion": device.get("offlineMKVersion", ""),
            "activeTime": device.get("activeTime", ""),
            "perDeviceType": device.get("perDeviceType", "0"),
            "pictureOnline": device.get("pictureOnline", ""),
            "pictureOffline": device.get("pictureOffline", ""),
            "lostBellEnable": device.get("lostBellEnable", False),
            "turboEnable": device.get("turboEnable", False),
            "sequenceAlias": device.get("sequenceAlias", 0),
            "abnormalDevice": device.get("abnormalDevice", 0),
        }

        # 解析定位信息
        locate_result = device.get("locateResult", {})
        if locate_result:
            result["locateResult"] = self._parse_locate_result(locate_result)

        # 解析唯一资源
        uniq_resource = device.get("uniqResource", {})
        if uniq_resource:
            result["coverUrl"] = uniq_resource.get("coverUrl", "")

        # 检查设备能力
        capabilities = result["capability"]
        result["canLocate"] = "locate" in capabilities
        result["canLock"] = "lockScreen" in capabilities
        result["canBell"] = "bell" in capabilities
        result["canLostPattern"] = "lostPattern" in capabilities
        result["canAlarm"] = "alarm" in capabilities
        result["canClear"] = "clear" in capabilities
        result["canTrackReport"] = "trackreport" in capabilities

        return result

    def _parse_locate_result(self, locate_result: Dict[str, Any]) -> Dict[str, Any]:
        """解析定位结果"""
        result = {
            "exeResult": locate_result.get("exeResult", ""),
            "code": locate_result.get("code", ""),
            "executeTime": locate_result.get("executeTime", 0),
            "currentTime": locate_result.get("currentTime", 0),
        }

        # 解析 locateInfo (JSON 字符串)
        locate_info_str = locate_result.get("locateInfo", "")
        if locate_info_str:
            try:
                locate_info = json.loads(locate_info_str)
                result["locateInfo"] = self._parse_locate_info(locate_info)
            except json.JSONDecodeError:
                result["locateInfo"] = locate_info_str

        # 解析 setting
        setting = locate_result.get("setting", {})
        if setting:
            result["setting"] = {
                "phoneNum": setting.get("phoneNum", ""),
                "email": setting.get("email", ""),
                "isNotifyChange": setting.get("isNotifyChange", False),
            }

        # 解析 cptLocateInfoList (配件定位)
        cpt_list = locate_result.get("cptLocateInfoList", [])
        if cpt_list:
            result["cptLocateInfoList"] = [
                self._parse_cpt_locate_info(cpt) for cpt in cpt_list
            ]

        return result

    def _parse_locate_info(self, locate_info: Dict[str, Any]) -> Dict[str, Any]:
        """解析 locateInfo 对象"""
        result = {}

        # 解析电池状态
        battery_str = locate_info.get("batteryStatus", "")
        if battery_str:
            try:
                battery = json.loads(battery_str)
                result["battery"] = {
                    "isCharging": battery.get("isCharging", "0"),
                    "percentage": battery.get("percentage", "0"),
                }
            except json.JSONDecodeError:
                result["batteryStatus"] = battery_str

        # 解析坐标信息
        coord_str = locate_info.get("coordinateInfo", "")
        if coord_str:
            try:
                coord = json.loads(coord_str)
                result["coordinate"] = {
                    "latitude": coord.get("latitude", 0),
                    "longitude": coord.get("longitude", 0),
                    "accuracy": coord.get("accuracy", ""),
                    "floor": coord.get("floor", ""),
                    "poi": coord.get("poi", ""),
                    "sysType": coord.get("sysType", ""),
                    "time": coord.get("time", ""),
                    "encryptVersion": coord.get("encryptVersion", 0),
                }
            except json.JSONDecodeError:
                result["coordinateInfo"] = coord_str

        # 解析网络信息
        network_str = locate_info.get("networkInfo", "")
        if network_str:
            try:
                network = json.loads(network_str)
                result["network"] = {
                    "name": network.get("name", ""),
                    "signal": network.get("signal", ""),
                    "type": network.get("type", ""),
                    "encryptVersion": network.get("encryptVersion", 0),
                }
            except json.JSONDecodeError:
                result["networkInfo"] = network_str

        # 解析 SIM 信息
        sim_str = locate_info.get("simInfo", "")
        if sim_str:
            try:
                sim = json.loads(sim_str)
                result["sim"] = {
                    "no": sim.get("no", ""),
                    "encryptVersion": sim.get("encryptVersion", 0),
                }
            except json.JSONDecodeError:
                result["simInfo"] = sim_str

        result["isLockScreen"] = locate_info.get("isLockScreen", 0)
        result["country"] = locate_info.get("country", "0")

        return result

    def _parse_cpt_locate_info(self, cpt_info: Dict[str, Any]) -> Dict[str, Any]:
        """解析配件定位信息"""
        result = {
            "connectType": cpt_info.get("connectType", -1),
            "cptList": cpt_info.get("cptList", ""),
            "country": cpt_info.get("country", "0"),
            "exceptionStatus": cpt_info.get("exceptionStatus", 0),
            "confidence": cpt_info.get("confidence", 0.0),
        }

        # 解析电池
        battery_str = cpt_info.get("batteryStatus", "")
        if battery_str:
            try:
                battery = json.loads(battery_str)
                result["battery"] = {"percentage": battery.get("percentage", "0")}
            except json.JSONDecodeError:
                pass

        # 解析坐标列表
        coord_list = cpt_info.get("coordinateInfoList", [])
        if coord_list:
            parsed_coords = []
            for coord_str in coord_list:
                try:
                    coord = json.loads(coord_str)
                    parsed_coords.append({
                        "latitude": coord.get("latitude", 0),
                        "longitude": coord.get("longitude", 0),
                        "accuracy": coord.get("accuracy", ""),
                        "time": coord.get("time", ""),
                        "type": coord.get("type", 0),
                    })
                except json.JSONDecodeError:
                    parsed_coords.append(coord_str)
            result["coordinateInfoList"] = parsed_coords

        return result

    # ---------- 设备操作 ----------

    def locate(self, device_id: str, device_type: int = 9, per_device_type: str = "0",
               cpt_list: str = "", endpoint_crypted: str = "1") -> Result:
        """发起设备定位

        Args:
            device_id: 设备 ID
            device_type: 设备类型，9=手机，2=平板
            per_device_type: 配件类型，"0"=主设备
            cpt_list: 配件列表
            endpoint_crypted: 是否端到端加密，"1"=是

        Returns:
            定位请求结果
        """
        url = f"{FIND_DEVICE_URL}/locate"
        body: Dict[str, Any] = {
            "deviceType": device_type,
            "deviceId": device_id,
            "perDeviceType": per_device_type,
            "cptList": cpt_list,
            "endpointCrypted": endpoint_crypted,
        }
        data = self._post(url, body, trace_prefix=TRACE_LOCATE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": data.get("info", "定位请求已发送") if code == "0" else f"失败({code})",
                "data": data}

    def query_locate_result(self, device_id: str, device_type: int = 9,
                            per_device_type: str = "0", sequence: int = 0,
                            endpoint_crypted: str = "1") -> Result:
        """查询定位结果

        Args:
            device_id: 设备 ID
            device_type: 设备类型
            per_device_type: 配件类型
            sequence: 查询序列号
            endpoint_crypted: 是否端到端加密

        Returns:
            包含经纬度、电池、网络等定位信息
        """
        url = f"{FIND_DEVICE_URL}/queryLocateResult"
        body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
            "perDeviceType": per_device_type,
            "sequence": sequence,
            "endpointCrypted": endpoint_crypted,
        }
        data = self._post(url, body, trace_prefix=TRACE_LOCATE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        exe_result = str(data.get("exeResult", "-1"))

        # 解析定位信息
        result_data: Dict[str, Any] = {
            "exeResult": exe_result,
            "executeTime": data.get("executeTime", 0),
            "currentTime": data.get("currentTime", 0),
        }

        # 解析 locateInfo
        locate_info_str = data.get("locateInfo", "")
        if locate_info_str:
            try:
                locate_info = json.loads(locate_info_str)
                result_data["locateInfo"] = self._parse_locate_info(locate_info)
            except json.JSONDecodeError:
                result_data["locateInfo"] = locate_info_str

        # 解析 setting
        setting = data.get("setting", {})
        if setting:
            result_data["setting"] = {
                "phoneNum": setting.get("phoneNum", ""),
                "email": setting.get("email", ""),
                "isNotifyChange": setting.get("isNotifyChange", False),
            }

        is_success = code == "0"
        return {"ok": is_success, "code": code,
                "msg": "定位成功" if is_success else f"查询失败({code})",
                "data": result_data}

    def play_bell(self, device_id: str, device_type: int = 9,
                  per_device_type: str = "0", cpt_list: str = "",
                  auto_locate: bool = True, locate_retry: int = 3,
                  locate_wait: float = 1.5) -> Result:
        """播放设备铃声

        Args:
            device_id: 设备 ID
            device_type: 设备类型
            per_device_type: 配件类型
            cpt_list: 配件列表
            auto_locate: 是否自动先发起定位唤醒设备（推荐开启，可提高成功率）
            locate_retry: 定位重试次数，默认 3 次
            locate_wait: 定位后等待秒数，默认 1.5 秒

        Returns:
            请求结果
        """
        # 先发起定位唤醒设备（根据抓包数据，响铃前需要先 locate）
        if auto_locate:
            for attempt in range(locate_retry):
                # 发起定位请求
                self.locate(
                    device_id=device_id,
                    device_type=device_type,
                    per_device_type=per_device_type,
                    cpt_list=cpt_list,
                )

                # 等待设备响应
                time.sleep(locate_wait)

                # 查询定位结果，确认设备在线
                location = self.query_locate_result(
                    device_id=device_id,
                    device_type=device_type,
                    per_device_type=per_device_type,
                )

                exe_result = str(location.get("data", {}).get("exeResult", "-1"))
                if exe_result == "0":
                    logger.info(f"设备 {device_id} 已在线，响铃准备就绪")
                    break
                else:
                    logger.warning(f"定位第 {attempt + 1} 次，设备未响应 (exeResult={exe_result})")
            else:
                logger.warning(f"定位重试 {locate_retry} 次后设备仍未响应，继续尝试响铃")

        # 发送响铃请求
        url = f"{FIND_DEVICE_URL}/portalBellReq"
        body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
            "perDeviceType": per_device_type,
            "cptList": cpt_list,
        }
        data = self._post(url, body, trace_prefix=TRACE_BELL)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))

        # 响铃成功后，查询确认
        if code == "0" and auto_locate:
            time.sleep(locate_wait)
            bell_result = self.query_locate_result(
                device_id=device_id,
                device_type=device_type,
                per_device_type=per_device_type,
            )
            exe_result = str(bell_result.get("data", {}).get("exeResult", "-1"))
            if exe_result == "0":
                logger.info(f"设备 {device_id} 响铃成功")
                return {"ok": True, "code": code,
                        "msg": "响铃成功", "data": data}
            else:
                return {"ok": True, "code": code,
                        "msg": "响铃请求已发送（设备未确认响应）", "data": data}

        return {"ok": code == "0", "code": code,
                "msg": "响铃请求已发送" if code == "0" else f"失败({code})",
                "data": data}

    def ring_device(self, device_id: str, device_type: int = 9,
                    max_wait_time: int = 30, check_interval: float = 2.0) -> Result:
        """完整的响铃接口（一站式）

        该接口封装了响铃的完整流程，包含所有步骤和错误检查：
        1. 检查设备是否存在
        2. 检查设备是否支持响铃
        3. 检查设备是否在线
        4. 发起定位唤醒
        5. 轮询等待设备响应
        6. 发送响铃请求
        7. 确认响铃结果

        如果中途任何步骤出现问题，会立即返回错误信息给用户。

        Args:
            device_id: 设备 ID
            device_type: 设备类型，默认 9（手机）
            max_wait_time: 最大等待设备响应时间（秒），默认 30 秒
            check_interval: 轮询检查间隔（秒），默认 2 秒

        Returns:
            Result: 包含以下字段：
                - ok: 是否成功
                - code: 状态码
                - msg: 详细信息
                - data: 包含详细结果数据
                    - device: 设备信息
                    - locate_attempts: 定位尝试次数
                    - total_time: 总耗时（秒）
        """
        import time
        start_time = time.time()
        result_data: Dict[str, Any] = {
            "device_id": device_id,
            "device_type": device_type,
            "steps": [],
        }

        def add_step(step_name: str, status: str, detail: str = ""):
            """记录步骤信息"""
            result_data["steps"].append({
                "step": step_name,
                "status": status,
                "detail": detail,
                "time": round(time.time() - start_time, 2),
            })

        # ========== 步骤1: 获取设备列表并检查设备 ==========
        add_step("获取设备列表", "进行中")
        devices_result = self.get_device_list()
        if not devices_result.get("ok"):
            add_step("获取设备列表", "失败", devices_result.get("msg", "未知错误"))
            return {
                "ok": False,
                "code": devices_result.get("code", "-1"),
                "msg": f"获取设备列表失败: {devices_result.get('msg')}",
                "data": result_data,
            }

        device_list = devices_result.get("data", {}).get("deviceList", [])
        target_device = None
        for device in device_list:
            if device.get("deviceId") == device_id:
                target_device = device
                break

        if not target_device:
            add_step("查找设备", "失败", f"设备ID {device_id[:16]}... 不在设备列表中")
            return {
                "ok": False,
                "code": "-1",
                "msg": f"设备不存在: 未找到ID为 {device_id[:16]}... 的设备",
                "data": result_data,
            }

        device_name = target_device.get("deviceAliasName", "未知设备")
        add_step("查找设备", "成功", f"找到设备: {device_name}")
        result_data["device"] = target_device

        # ========== 步骤2: 检查设备能力 ==========
        add_step("检查设备能力", "进行中")
        if not target_device.get("canBell"):
            add_step("检查设备能力", "失败", "设备不支持响铃功能")
            return {
                "ok": False,
                "code": "-1",
                "msg": f"设备 '{device_name}' 不支持响铃功能",
                "data": result_data,
            }
        add_step("检查设备能力", "成功", "设备支持响铃")

        # ========== 步骤3: 检查设备在线状态 ==========
        add_step("检查在线状态", "进行中")
        is_online = target_device.get("offlineStatus") == 1
        if not is_online:
            add_step("检查在线状态", "警告", "设备当前离线，响铃可能失败")
            # 不离线直接返回，继续尝试
        else:
            add_step("检查在线状态", "成功", "设备在线")

        # ========== 步骤4: 发起定位唤醒 ==========
        add_step("发起定位唤醒", "进行中")
        locate_result = self.locate(device_id, device_type)
        if not locate_result.get("ok"):
            add_step("发起定位唤醒", "失败", locate_result.get("msg", "未知错误"))
            return {
                "ok": False,
                "code": locate_result.get("code", "-1"),
                "msg": f"定位唤醒失败: {locate_result.get('msg')}",
                "data": result_data,
            }
        add_step("发起定位唤醒", "成功", "定位请求已发送")

        # ========== 步骤5: 轮询等待设备响应 ==========
        add_step("等待设备响应", "进行中")
        max_attempts = int(max_wait_time / check_interval)
        locate_attempts = 0
        device_responded = False

        for attempt in range(max_attempts):
            time.sleep(check_interval)
            locate_attempts += 1

            query_result = self.query_locate_result(device_id, device_type)
            if not query_result.get("ok"):
                add_step("等待设备响应", "查询失败", query_result.get("msg"))
                continue

            exe_result = str(query_result.get("data", {}).get("exeResult", "-1"))
            if exe_result == "0":
                device_responded = True
                add_step("等待设备响应", "成功", f"设备已响应（第{attempt + 1}次查询）")
                break
            else:
                logger.debug(f"第 {attempt + 1} 次查询，设备未响应 (exeResult={exe_result})")

        result_data["locate_attempts"] = locate_attempts

        if not device_responded:
            add_step("等待设备响应", "超时", f"{max_wait_time}秒内设备未响应")
            return {
                "ok": False,
                "code": "-1",
                "msg": f"设备未响应: 等待 {max_wait_time} 秒后设备仍未上线，请检查设备网络连接",
                "data": result_data,
            }

        # ========== 步骤6: 发送响铃请求 ==========
        add_step("发送响铃请求", "进行中")
        bell_url = f"{FIND_DEVICE_URL}/portalBellReq"
        bell_body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
            "perDeviceType": "0",
            "cptList": "",
        }
        bell_data = self._post(bell_url, bell_body, trace_prefix=TRACE_BELL)

        if "error" in bell_data:
            add_step("发送响铃请求", "失败", bell_data["error"])
            return {
                "ok": False,
                "code": bell_data.get("_code", "-1"),
                "msg": f"响铃请求失败: {bell_data['error']}",
                "data": result_data,
            }

        bell_code = str(bell_data.get("code", ""))
        if bell_code != "0":
            add_step("发送响铃请求", "失败", f"返回码: {bell_code}")
            return {
                "ok": False,
                "code": bell_code,
                "msg": f"响铃请求被拒绝: {bell_data.get('info', f'错误码 {bell_code}')}",
                "data": result_data,
            }

        add_step("发送响铃请求", "成功", "响铃指令已发送至设备")

        # ========== 步骤7: 确认响铃结果 ==========
        add_step("确认响铃结果", "进行中")
        time.sleep(check_interval)  # 等待设备执行

        confirm_result = self.query_locate_result(device_id, device_type)
        if confirm_result.get("ok"):
            final_exe_result = str(confirm_result.get("data", {}).get("exeResult", "-1"))
            if final_exe_result == "0":
                add_step("确认响铃结果", "成功", "设备确认执行响铃")
            else:
                add_step("确认响铃结果", "警告", f"设备未确认 (exeResult={final_exe_result})")
        else:
            add_step("确认响铃结果", "警告", "无法查询最终结果")

        total_time = round(time.time() - start_time, 2)
        result_data["total_time"] = total_time

        return {
            "ok": True,
            "code": "0",
            "msg": f"响铃成功！设备 '{device_name}' 应该正在响铃",
            "data": result_data,
        }

    def query_bell_result(self, device_id: str, device_type: int,
                          per_device_type: str = "0", sequence: int = 0) -> Result:
        """查询响铃结果

        Args:
            device_id: 设备 ID
            device_type: 设备类型
            per_device_type: 配件类型
            sequence: 查询序列号

        Returns:
            响铃结果
        """
        url = f"{FIND_DEVICE_URL}/queryportalBellReqResult"
        body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
            "perDeviceType": per_device_type,
            "sequence": sequence,
        }
        data = self._post(url, body, trace_prefix=TRACE_BELL)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        exe_result = str(data.get("exeResult", ""))
        return {"ok": code == "0", "code": code,
                "msg": "响铃成功" if exe_result == "0" else f"响铃未完成({exe_result})",
                "data": {
                    "exeResult": exe_result,
                    "executeTime": data.get("executeTime", 0),
                }}

    # ---------- 丢失模式 ----------

    def start_lost_mode(self, device_id: str, device_type: int = 9,
                        message: str = "", phone_num: str = "",
                        email: str = "", lock_screen: str = "",
                        lock_sdcard: str = "", country_calling_code: str = "+86",
                        endpoint_crypted: str = "1",
                        is_notify_change: bool = True) -> Result:
        """开启丢失模式

        Args:
            device_id: 设备 ID
            device_type: 设备类型
            message: 留言信息
            phone_num: 联系电话（含国家码格式，如 +86138****8888）
            email: 联系邮箱
            lock_screen: 锁定屏幕密码
            lock_sdcard: 锁定 SD 卡密码
            country_calling_code: 国际区号，默认 +86
            endpoint_crypted: 是否端到端加密
            is_notify_change: 是否通知变更，首次开启设为 True，修改信息时设为 False

        Returns:
            操作结果
        """
        url = f"{FIND_DEVICE_URL}/startLostPattern"
        body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
            "lockScreen": lock_screen,
            "lockSdcard": lock_sdcard,
            "endpointCrypted": endpoint_crypted,
            "isSingleFrameClient": True,
            "message": message,
            "phoneNum": phone_num,
            "email": email,
            "isNotifyChange": is_notify_change,
            "countryCallingCode": country_calling_code,
        }
        data = self._post(url, body, trace_prefix=TRACE_LOST_MODE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        
        # 错误码映射
        error_messages = {
            "010001": "手机号格式错误",
            "010002": "设备不支持丢失模式",
            "010003": "设备离线",
        }
        
        if code == "0":
            msg = "丢失模式已开启"
        elif code in error_messages:
            msg = f"{error_messages[code]}({code})"
        else:
            msg = f"失败({code})"
        
        return {"ok": code == "0", "code": code, "msg": msg, "data": data}

    def stop_lost_mode(self, device_id: str, device_type: int = 9) -> Result:
        """关闭丢失模式

        Args:
            device_id: 设备 ID
            device_type: 设备类型

        Returns:
            操作结果
        """
        url = f"{FIND_DEVICE_URL}/stopLostPattern"
        body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
        }
        data = self._post(url, body, trace_prefix=TRACE_LOST_MODE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "丢失模式已关闭" if code == "0" else f"失败({code})",
                "data": data}

    def query_lost_mode_info(self, device_id: str, device_type: int = 9) -> Result:
        """查询丢失模式信息

        Args:
            device_id: 设备 ID
            device_type: 设备类型

        Returns:
            包含留言、联系电话、是否开启等
        """
        url = f"{FIND_DEVICE_URL}/queryopenPatternParInfo"
        body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
            "operation": "queryLostPattern",
        }
        data = self._post(url, body, trace_prefix=TRACE_PATTERN)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        result_data = {
            "message": data.get("message", ""),
            "phoneNum": data.get("phoneNum", ""),
            "isNotifyChange": data.get("isNotifyChange", "false"),
            "isCrypt": data.get("isCrypt", 0),
            "openLostPattern": data.get("openLostPattern", False),
        }
        return {"ok": code == "0", "code": code,
                "msg": "丢失模式信息" if code == "0" else f"失败({code})",
                "data": result_data}

    def query_cmd_result(self, device_id: str, device_type: int = 9,
                        cmds: Optional[List[str]] = None,
                        per_device_type: str = "0") -> Result:
        """查询设备命令执行结果

        这是一个通用接口，用于查询设备端执行命令（如清除数据、锁定屏幕等）的结果。
        常见的命令包括: openLostPattern, stopLostPattern, clear, lockScreen 等。

        Args:
            device_id: 设备 ID
            device_type: 设备类型
            cmds: 要查询的命令列表，默认 ["openLostPattern", "stopLostPattern", "clear"]
            per_device_type: 配件类型

        Returns:
            命令执行结果
        """
        url = f"{FIND_DEVICE_URL}/getCmdResult"
        body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
            "perDeviceType": per_device_type,
            "cmds": cmds or ["openLostPattern", "stopLostPattern", "clear"],
        }
        data = self._post(url, body, trace_prefix=TRACE_CMD_RESULT)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": data.get("info", "命令结果查询"),
                "data": data}

    # TODO: 擦除设备功能未实现
    # 原因: 由于没有实机测试，为避免误操作导致数据丢失，暂未实现该功能。
    # 相关接口可能为: /findDevice/clear 或 /findDevice/erase
    # 设备能力通过 canClear 字段标识
    # def erase_device(self, device_id: str, device_type: int = 9) -> Result:
    #     """擦除设备数据（恢复出厂设置）
    #
    #     警告: 此操作会清除设备所有数据，请谨慎使用！
    #
    #     Args:
    #         device_id: 设备 ID
    #         device_type: 设备类型
    #
    #     Returns:
    #         操作结果
    #     """
    #     pass

    def query_country_calling_code(self, lang: str = "zh-cn") -> Result:
        """查询国际区号列表

        Args:
            lang: 语言代码，默认 "zh-cn"

        Returns:
            包含国家/地区代码映射和默认区号
        """
        url = f"{FIND_DEVICE_URL}/queryCountryCallingCode"
        body: Dict[str, Any] = {"lang": lang}
        data = self._post(url, body, trace_prefix=TRACE_DEVICE_LIST)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        if code != "0":
            return {"ok": False, "code": code,
                    "msg": data.get("info", f"失败({code})"), "data": {}}

        # 解析 countryMap JSON 字符串
        country_map_str = data.get("countryMap", "[]")
        country_list = []
        try:
            country_list = json.loads(country_map_str)
        except json.JSONDecodeError:
            pass

        return {"ok": True, "code": code,
                "msg": f"{len(country_list)}个国家/地区",
                "data": {
                    "countryMap": country_list,
                    "defaultCallingCode": data.get("defaultCallingCode", "+86"),
                }}

    def report_map_health(self, map_type: str = "hmap", status: str = "0") -> Result:
        """上报地图健康状态

        Args:
            map_type: 地图类型，默认 "hmap"
            status: 状态码，默认 "0"

        Returns:
            上报结果
        """
        url = f"{FIND_DEVICE_URL}/reportMapHealth"
        body: Dict[str, Any] = {
            "mapType": map_type,
            "status": status,
        }
        data = self._post(url, body, trace_prefix=TRACE_MAP_HEALTH)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": True, "code": code,
                "msg": "地图健康上报", "data": data}

    # ---------- 轨迹 ----------

    def query_tracks(self, device_id: str, device_type: int = 9,
                     origin_info: Optional[Dict[str, Any]] = None,
                     execute_time: int = 0, track_type: int = 1,
                     endpoint_crypted: str = "1") -> Result:
        """查询设备轨迹

        Args:
            device_id: 设备 ID
            device_type: 设备类型
            origin_info: 起始信息
            execute_time: 执行时间
            track_type: 轨迹类型，1=当前位置
            endpoint_crypted: 是否端到端加密

        Returns:
            包含轨迹点列表
        """
        url = f"{FIND_DEVICE_URL}/queryTracksList"
        body: Dict[str, Any] = {
            "deviceId": device_id,
            "deviceType": device_type,
            "originInfo": origin_info or {},
            "executeTime": execute_time,
            "type": track_type,
            "endpointCrypted": endpoint_crypted,
        }
        data = self._post(url, body, trace_prefix=TRACE_TRACKS)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        if code != "0":
            return {"ok": False, "code": code,
                    "msg": data.get("info", f"失败({code})"), "data": {}}

        # 解析轨迹点
        tracks = data.get("tracks", [])
        parsed_tracks = [self._parse_track(t) for t in tracks]

        return {"ok": True, "code": code,
                "msg": f"{len(tracks)}个轨迹点", "data": {"tracks": parsed_tracks}}

    def _parse_track(self, track: Dict[str, Any]) -> Dict[str, Any]:
        """解析轨迹点"""
        create_time = track.get("createTime", 0)
        result = {
            "simSn": track.get("simSn", ""),
            "isLockScreen": track.get("isLockScreen", 0),
            "createTime": create_time,
            "createTime_str": datetime.fromtimestamp(create_time / 1000).strftime("%Y-%m-%d %H:%M:%S") if create_time else "",
        }

        # 解析坐标信息
        coord_info = track.get("coordinateInfo", {})
        if coord_info:
            result["coordinate"] = {
                "latitude": coord_info.get("latitude", ""),
                "longitude": coord_info.get("longitude", ""),
                "type": coord_info.get("type", 0),
                "accuracy": coord_info.get("accuracy", ""),
                "sysType": coord_info.get("sysType", ""),
                "time": coord_info.get("time", ""),
                "floor": coord_info.get("floor", ""),
                "poi": coord_info.get("poi", ""),
            }

        return result

    # ---------- 辅助方法 ----------

    def get_device_by_name(self, name: str) -> Result:
        """根据设备名称获取设备信息

        Args:
            name: 设备名称（模糊匹配）

        Returns:
            匹配的设备信息，未找到返回空
        """
        result = self.get_device_list()
        if not result.get("ok"):
            return result

        device_list = result.get("data", {}).get("deviceList", [])
        for device in device_list:
            if name in device.get("deviceAliasName", ""):
                return {"ok": True, "code": "0",
                        "msg": "找到设备", "data": device}

        return {"ok": False, "code": "-1", "msg": f"未找到设备: {name}", "data": {}}

    def get_online_devices(self) -> Result:
        """获取在线设备列表"""
        result = self.get_device_list()
        if not result.get("ok"):
            return result

        device_list = result.get("data", {}).get("deviceList", [])
        online = [d for d in device_list if d.get("offlineStatus") == 1]
        return {"ok": True, "code": "0",
                "msg": f"{len(online)}个在线设备", "data": {"deviceList": online}}

    def get_locatable_devices(self) -> Result:
        """获取支持定位的设备列表"""
        result = self.get_device_list()
        if not result.get("ok"):
            return result

        device_list = result.get("data", {}).get("deviceList", [])
        locatable = [d for d in device_list if d.get("canLocate")]
        return {"ok": True, "code": "0",
                "msg": f"{len(locatable)}个可定位设备", "data": {"deviceList": locatable}}
