"""华为云空间 · 联系人模块

基于抓包数据验证的 API 接口封装。

简化用法::

    # 传入简化字典，自动解析
    client.contacts.create_contact({"name": "张三", "phone": "13800138000"})
    client.contacts.create_contact({"name": "李四", "phone": "13900139000", "email": "lisi@qq.com"})

    # 更新联系人
    client.contacts.update_contact({"contact_id": "xxx", "name": "王五"})
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Union

from .base import BaseModule, Result, _generate_traceid

logger = logging.getLogger("cloud-space-huawei.contacts")


def _check_image_size(source: str, size: int = 162) -> Optional[bool]:
    """检测图片是否为指定尺寸的正方形

    Args:
        source: 本地文件路径 或 Base64 字符串
        size: 目标正方形边长（默认 162）

    Returns:
        True  — 已经是 size×size 的正方形，无需处理
        False — 不是目标尺寸，需要裁切/上传
        None  — 无法检测（Pillow 未安装等），需走常规流程
    """
    import base64
    import io
    import os

    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        if os.path.isfile(source):
            img = Image.open(source)
        else:
            img_bytes = base64.b64decode(source)
            img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size
        return w == size and h == size
    except Exception:
        return None


def _image_to_base64(path: str) -> str:
    """将本地图片文件直接转为 Base64（不做任何处理）"""
    import base64

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _crop_square_base64(b64_data: str, size: int = 162) -> str:
    """将 Base64 图片居中裁切为正方形并缩放到指定尺寸

    如果图片已经是 size×size 的正方形，直接返回原始数据，不做处理。

    Args:
        b64_data: 原始 Base64 编码的图片数据
        size: 输出正方形图片的像素边长（默认 162）

    Returns:
        裁切后的 Base64 编码 JPEG 图片
    """
    import base64
    import io

    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow 未安装，跳过图片裁切，使用原始图片")
        return b64_data

    img_bytes = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(img_bytes))

    w, h = img.size

    # 已经是目标尺寸的正方形，直接返回
    if w == size and h == size:
        return b64_data

    # 居中裁切为正方形
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # 缩放到目标尺寸
    if side != size:
        # Pillow >=9.1 使用 Image.Resampling.LANCZOS，旧版使用 Image.LANCZOS
        _resampling = getattr(Image, "Resampling", Image)
        resample = getattr(_resampling, "LANCZOS", 1)  # 1 = Image.LANCZOS
        img = img.resize((size, size), resample)

    # 转回 Base64
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ============================================================
# 联系人字段 type 枚举（基于网页 UI + 抓包验证）
# ============================================================
# type=0 均为"自定义"，此时 name 字段可填写自定义标签名。
# 超出最大值的 type 服务端会丢弃该条目，请勿越界。

TEL_TYPES = {
    1: "手机",
    2: "住宅",
    3: "单位",
    14: "总机",
    5: "单位传真",
    6: "住宅传真",
    7: "寻呼机",
    8: "其它",
    0: "自定义",   # name 必填
}
TEL_TYPE_MAX = 14

EMAIL_TYPES = {
    1: "私人",
    2: "单位",
    3: "其它",
    0: "自定义",   # name 必填
}
EMAIL_TYPE_MAX = 3

IM_TYPES = {
    1: "AIM",
    2: "Windows Live",
    3: "雅虎",
    4: "Skype",
    5: "QQ",
    6: "环聊",
    7: "ICQ",
    8: "Jabber",
    0: "自定义",   # name 必填
}
IM_TYPE_MAX = 8

ADDRESS_TYPES = {
    1: "住宅",
    2: "单位",
    3: "其它",
    0: "自定义",   # name 必填
}
ADDRESS_TYPE_MAX = 3

DATE_TYPES = {
    1: "生日",
    # type=2 为农历生日，dateList 中 type=2 会由服务端自动合并到 bDayLunar
    2: "农历生日",
    3: "周年纪念",
    4: "其它重要日期",
}
DATE_TYPE_MAX = 4

# 网站没有 type，urlList 条目中 type 字段可省略或为任意值
URL_TYPE_MAX = 0

RELATION_TYPES = {
    1:  "助理",
    2:  "弟兄",
    3:  "子女",
    4:  "合作伙伴",
    5:  "父亲",
    6:  "朋友",
    7:  "上司",
    8:  "母亲",
    9:  "父母",
    10: "伴侣",
    11: "介绍人",
    12: "亲属",
    13: "姐妹",
    14: "配偶",
    0:  "自定义",   # name 必填
}
RELATION_TYPE_MAX = 14

EVENT_TYPES = {
    1: "事件",
}
EVENT_TYPE_MAX = 1


# ============================================================
# 简化字典 → API 请求体 自动解析
# ============================================================

# 简化字段名 → API 字段路径映射
_SIMPLE_KEY_MAP = {
    "name":        "name.firstName",
    "last_name":   "name.lastName",
    "middle_name": "name.middleName",
    "prefix":      "name.namePrefix",
    "suffix":      "name.nameSuffix",
    "phone":       "telList",       # 特殊: 自动包装为 [{"type":1,"value":"...","name":""}]
    "email":       "emailList",     # 特殊: 自动包装为 [{"type":1,"value":"...","name":""}]
    "org":         "organizeList",  # 特殊: str→[{"org":"xxx"}] 或 dict→[{"org":"xxx","title":"yyy"}]
    "im":          "msgList",       # 特殊: 自动包装为 [{"type":1,"value":"...","name":""}]
    "address":     "addressList",   # 特殊: str→[{"type":1,"street":"xxx","name":""}] 或 dict/list
    "url":         "urlList",       # 特殊: 自动包装为 [{"value":"..."}]，无 type/name
    "date":        "dateList",      # 特殊: 自动包装为 [{"type":3,"value":"...","name":""}]
    "event":       "eventList",     # 特殊: 自动包装为 [{"type":1,"value":"...","name":""}]
    "relation":    "relationList",  # 特殊: 自动包装为 [{"type":1,"value":"...","name":""}]
    "nickname":    "nickName",
    "note":        "note",
    # birthday_lunar 通过 dateList type=2 实现，服务端自动填充 bDayLunar，不走 _SIMPLE_KEY_MAP
    "photo":       "photoUrl",
    "contact_id":  "contactId",
    "uid":         "uId",
    "group_ids":   "groupIdList",
    "group_names": "groupName",
}


def _wrap_tel(phone: str, tel_type: int = 1) -> Dict[str, Any]:
    """将电话号码字符串包装为 API 格式"""
    return {"type": tel_type, "value": phone, "name": ""}


def _wrap_email(email: str, email_type: int = 1) -> Dict[str, Any]:
    """将邮箱字符串包装为 API 格式"""
    return {"type": email_type, "value": email, "name": ""}


def _set_nested(d: Dict[str, Any], path: str, value: Any) -> None:
    """按点分路径设置嵌套字典值，如 'name.firstName' → d['name']['firstName']"""
    keys = path.split(".")
    for key in keys[:-1]:
        d.setdefault(key, {})
        d = d[key]
    d[keys[-1]] = value


def parse_simple_contact(info: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """将简化字典解析为 API 请求体格式

    简化字段映射::

        name           → 名 (firstName)
        last_name      → 姓 (lastName)
        middle_name    → 中间名
        prefix         → 姓名前缀
        suffix         → 姓名后缀
        phone          → 电话号码 (自动包装为 telList)
        email          → 邮箱 (自动包装为 emailList)
        org            → 工作单位 (str 或 dict，自动包装为 organizeList)
        im             → 即时通讯 (str/list，自动包装为 msgList)
        address        → 地址 (str/dict/list，自动包装为 addressList)
        url            → 网站 (str/list，自动包装为 urlList，无 type/name)
        date           → 日期 (str/list，自动包装为 dateList)
        event          → 事件 (str/list，自动包装为 eventList)
        relation       → 关系 (str/list，自动包装为 relationList)
        nickname       → 昵称 (仅电脑端云空间可见，手机端不显示)
        note           → 备注
        birthday       → 生日 (自动设置 dateList type=1 和 bDay)
        birthday_lunar → 农历生日 (值格式与birthday相同，自动设置 dateList type=2，服务端自动填充 bDayLunar，手机端自动转换为公历显示)
        photo          → 头像 (文件路径 / Base64 / {"file":"..."} / {"base64":"..."}，create/update 时自动处理)
        contact_id     → 联系人ID (更新时必填)
        uid            → 联系人UID
        groups        → 群组 (dict/list，自动展开为 groupIdList + groupName + groupObj)
        group_ids     → 群组ID列表 (仅电脑端云空间可见，手机端不显示)
        group_names   → 群组名称列表 (仅电脑端云空间可见，手机端不显示)

    注意:
        - 群组功能仅在电脑端云空间可见，手机端不显示

    特殊处理:
        - groups 支持 dict(单个群组) 或 list(多个群组)，每项含 group_id 和 group_name
        - phone 支持 str(单个) 或 list(多个)
        - email 支持 str(单个) 或 list(多个)
        - org 支持 str("公司名") 或 dict({"org":"公司","title":"职位"})
        - im 支持 str(单个) 或 list(多个)
        - address 支持 str("地址")、dict({"street":"xxx","type":1}) 或 list
        - url 支持 str(单个) 或 list(多个)
        - date 支持 str("2003-08-23") 或 list
        - event 支持 str(单个) 或 list(多个)
        - relation 支持 str(单个) 或 list(多个)
        - 未识别的 key 原样保留（用于直接传 API 字段）

    示例::

        parse_simple_contact({"name": "张三", "phone": "13800138000"})
        parse_simple_contact({"name": "李四", "phone": ["138", "139"], "email": "a@b.com"})
        parse_simple_contact({"name": "王五", "org": "华为", "note": "同事"})
        parse_simple_contact({"name": "赵六", "org": {"org": "华为", "title": "工程师"}})
    """
    # 提前取出 groups（特殊虚拟字段，不写入 contact 对象）
    groups_value = info.get("groups")

    contact: Dict[str, Any] = {
        "contactId": "",
        "uId": "",
        "groupIdList": [],
        "name": {
            "firstName": "",
            "middleName": "",
            "lastName": "",
            "namePrefix": "",
            "nameSuffix": "",
        },
        "organizeList": [],
        "addressList": [],
        "emailList": [],
        "msgList": [],
        "telList": [],
        "urlList": [],
        "eventList": [],
        "dateList": [],
        "relationList": [],
        "bDay": "",
        "bDayLunar": "",
        "nickName": "",
        "note": "",
        "photoUrl": "",
        "groupName": [],
    }

    for key, value in info.items():
        if value is None:
            continue

        # groups 是虚拟字段，由 create/update 方法单独处理，跳过
        if key == "groups":
            continue

        # birthday 特殊处理: 映射到 dateList type=1(生日)，同时设置 bDay
        if key == "birthday":
            contact["bDay"] = value
            if value:
                contact["dateList"] = [{"type": 1, "value": value, "name": ""}]
            continue

        # birthday_lunar 特殊处理: 映射到 dateList type=2(农历生日)，服务端自动填充 bDayLunar
        if key == "birthday_lunar":
            if value:
                contact["dateList"] = [{"type": 2, "value": value, "name": ""}]
            continue

        # phone 特殊处理: str → [wrap], list → [wrap, ...]
        if key == "phone":
            if isinstance(value, str):
                contact["telList"] = [_wrap_tel(value)]
            elif isinstance(value, list):
                contact["telList"] = [_wrap_tel(p) if isinstance(p, str) else p for p in value]
            else:
                contact["telList"] = value
            continue

        # email 特殊处理
        if key == "email":
            if isinstance(value, str):
                contact["emailList"] = [_wrap_email(value)]
            elif isinstance(value, list):
                contact["emailList"] = [_wrap_email(e) if isinstance(e, str) else e for e in value]
            else:
                contact["emailList"] = value
            continue

        # org 特殊处理: str→[{"org":"xxx"}], dict→[{"org":"xxx","title":"yyy"}]
        if key == "org":
            if isinstance(value, str):
                contact["organizeList"] = [{"org": value, "title": ""}]
            elif isinstance(value, dict):
                contact["organizeList"] = [value]
            elif isinstance(value, list):
                contact["organizeList"] = [
                    {"org": v, "title": ""} if isinstance(v, str) else v for v in value
                ]
            else:
                contact["organizeList"] = value
            continue

        # im 特殊处理: str→[{"type":1,"value":"xxx","name":""}], list同理
        if key == "im":
            if isinstance(value, str):
                contact["msgList"] = [{"type": 1, "value": value, "name": ""}]
            elif isinstance(value, list):
                contact["msgList"] = [
                    {"type": 1, "value": v, "name": ""} if isinstance(v, str) else v for v in value
                ]
            else:
                contact["msgList"] = value
            continue

        # address 特殊处理: str→[{"type":1,"street":"xxx","name":""}], dict→[dict], list同理
        if key == "address":
            if isinstance(value, str):
                contact["addressList"] = [{"type": 1, "street": value, "name": ""}]
            elif isinstance(value, dict):
                value.setdefault("type", 1)
                value.setdefault("name", "")
                value.setdefault("street", "")
                contact["addressList"] = [value]
            elif isinstance(value, list):
                contact["addressList"] = [
                    {"type": 1, "street": v, "name": ""} if isinstance(v, str) else v for v in value
                ]
            else:
                contact["addressList"] = value
            continue

        # url 特殊处理: str→[{"value":"xxx"}]，无 type/name
        if key == "url":
            if isinstance(value, str):
                contact["urlList"] = [{"value": value}]
            elif isinstance(value, list):
                contact["urlList"] = [
                    {"value": v} if isinstance(v, str) else v for v in value
                ]
            else:
                contact["urlList"] = value
            continue

        # date 特殊处理: str→[{"type":3,"value":"xxx","name":""}], list同理
        # type: 1=生日(用birthday), 2=农历生日(用birthday_lunar), 3=周年纪念(默认), 4=其它
        if key == "date":
            if isinstance(value, str):
                contact["dateList"] = [{"type": 3, "value": value, "name": ""}]
            elif isinstance(value, list):
                contact["dateList"] = [
                    {"type": 3, "value": v, "name": ""} if isinstance(v, str) else v for v in value
                ]
            else:
                contact["dateList"] = value
            continue

        # event 特殊处理: str→[{"type":1,"value":"xxx","name":""}], list同理
        if key == "event":
            if isinstance(value, str):
                contact["eventList"] = [{"type": 1, "value": value, "name": ""}]
            elif isinstance(value, list):
                contact["eventList"] = [
                    {"type": 1, "value": v, "name": ""} if isinstance(v, str) else v for v in value
                ]
            else:
                contact["eventList"] = value
            continue

        # relation 特殊处理: str→[{"type":1,"value":"xxx","name":""}], list同理
        if key == "relation":
            if isinstance(value, str):
                contact["relationList"] = [{"type": 1, "value": value, "name": ""}]
            elif isinstance(value, list):
                contact["relationList"] = [
                    {"type": 1, "value": v, "name": ""} if isinstance(v, str) else v for v in value
                ]
            else:
                contact["relationList"] = value
            continue

        # 已知简化 key → API 路径
        if key in _SIMPLE_KEY_MAP:
            _set_nested(contact, _SIMPLE_KEY_MAP[key], value)
            continue

        # 未知 key: 尝试直接设置到 contact 顶层 (兼容直接传 API 字段)
        contact[key] = value

    # 从 groups 构建 groupIdList / groupName / groupObj
    group_obj: List[Dict[str, Any]] = []
    if groups_value:
        groups_list = [groups_value] if isinstance(groups_value, dict) else groups_value
        contact["groupIdList"] = [g["group_id"] for g in groups_list]
        contact["groupName"] = [g["group_name"] for g in groups_list]
        group_obj = [
            {
                "groupId": g["group_id"],
                "groupName": g["group_name"],
                "contactIdList": g.get("contact_id_list", []),
                "contactUuIdList": g.get("contact_uuid_list", []),
            }
            for g in groups_list
        ]

    return contact, group_obj


# ============================================================
# 联系人模块
# ============================================================

class ContactsModule(BaseModule):
    """华为云联系人

    通过 HuaweiCloudClient.contacts 访问。

    简化用法::

        # 创建 — 传字典，自动解析
        client.contacts.create_contact({"name": "张三", "phone": "13800138000"})

        # 更新 — 传字典含 contact_id
        client.contacts.update_contact({"contact_id": "xxx", "name": "王五"})
    """

    # ---------- 结果解析 ----------

    @staticmethod
    def _is_success(data: Dict[str, Any]) -> bool:
        """判断联系人 API 响应是否成功

        联系人模块使用 result.resultCode 而非顶层 code。
        """
        result = data.get("result", {})
        code = str(result.get("resultCode", ""))
        return code == "0"

    # ---------- 联系人 CRUD ----------

    def get_contacts(self, soft_del: str = "0") -> Result:
        """获取全部联系人列表

        Args:
            soft_del: "0" = 正常联系人, "1" = 回收站中的联系人
        """
        url = f"{self.BASE_URL}/contact/getAllContacts"
        body: Dict[str, Any] = {"softDel": soft_del}
        data = self._post(url, body, trace_prefix="03111")
        if self._is_success(data):
            data["ok"] = True
        return data

    def query_contacts_by_page(self, soft_del: str = "0") -> Result:
        """分页查询联系人

        Args:
            soft_del: "0" = 正常联系人, "1" = 回收站中的联系人
        """
        url = f"{self.BASE_URL}/contact/queryContactsByPage"
        body: Dict[str, Any] = {"softDel": soft_del}
        data = self._post(url, body, trace_prefix="03111")
        if self._is_success(data):
            data["ok"] = True
        return data

    def get_design_contact(self, contact_ids: List[str]) -> Result:
        """获取指定联系人详情

        Args:
            contact_ids: 联系人ID列表（如 ["FsuGCA_OIZMv7kAS8BI9Pqbv9m70QiG3L"]）
        """
        url = f"{self.BASE_URL}/contact/getDesignContact"
        body: Dict[str, Any] = {"contactIds": contact_ids}
        data = self._post(url, body, trace_prefix="03111")
        if self._is_success(data):
            data["ok"] = True
        return data

    def _resolve_photo(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """预处理 photo 字段，自动完成图片上传和裁切

        photo 支持以下格式::

            "photo.jpg"                           — 本地文件路径，自动上传到 previewImg 并裁切
            {"file": "photo.jpg"}                 — 同上，显式指定文件路径
            {"base64": "iVBORw0KGgo..."}          — 直接传入 base64，仅裁切不上传
            "iVBORw0KGgo..."                      — 原始 base64 字符串（兼容旧用法）

        如果图片已经是 162×162 正方形，则跳过上传和裁切，直接转 Base64。

        处理完成后会将 photo 替换为 base64 字符串，
        后续 parse_simple_contact 会将其映射为 photoUrl。
        """
        import os

        photo_value = info.get("photo")
        if photo_value is None:
            return info

        info = dict(info)  # 不修改原始 dict

        # dict 格式: {"file": "..."} 或 {"base64": "..."}
        if isinstance(photo_value, dict):
            file_path = photo_value.get("file")
            b64_data = photo_value.get("base64")
            if file_path:
                # 检测是否已是目标尺寸，如果是则跳过上传直接转 base64
                if _check_image_size(file_path) is True:
                    info["photo"] = _image_to_base64(file_path)
                    return info
                result = self.preview_img(file_path)
                if not result.get("ok"):
                    logger.warning("photo 上传失败: %s", result.get("error", ""))
                    info.pop("photo", None)
                    return info
                info["photo"] = result["photoUrl"]
            elif b64_data:
                # 检测 base64 图片是否已是目标尺寸
                if _check_image_size(b64_data) is True:
                    info["photo"] = b64_data
                    return info
                result = self.preview_img(b64_data, is_base64=True)
                info["photo"] = result["photoUrl"]
            return info

        # 字符串格式
        if isinstance(photo_value, str):
            # 判断是文件路径还是 base64
            if os.path.isfile(photo_value):
                # 检测是否已是目标尺寸，如果是则跳过上传直接转 base64
                if _check_image_size(photo_value) is True:
                    info["photo"] = _image_to_base64(photo_value)
                    return info
                result = self.preview_img(photo_value)
                if not result.get("ok"):
                    logger.warning("photo 上传失败: %s", result.get("error", ""))
                    info.pop("photo", None)
                    return info
                info["photo"] = result["photoUrl"]
            else:
                # 当作 base64 处理
                if _check_image_size(photo_value) is True:
                    info["photo"] = photo_value
                    return info
                result = self.preview_img(photo_value, is_base64=True)
                info["photo"] = result["photoUrl"]
            return info

        return info

    def create_contact(
        self,
        info: Dict[str, Any],
        *,
        group_obj: Optional[List[Dict[str, Any]]] = None,
    ) -> Result:
        """创建联系人（传入简化字典，自动解析）

        Args:
            info: 简化联系人信息字典，支持的 key::

                name        — 名
                last_name   — 姓
                phone       — 电话号码 (str 或 list)
                email       — 邮箱 (str 或 list)
                nickname    — 昵称
                note        — 备注
                birthday    — 生日
                photo       — 头像，支持以下格式::

                    "photo.jpg"                  — 本地文件路径，自动上传并裁切
                    {"file": "photo.jpg"}        — 显式指定文件路径
                    {"base64": "iVBORw0KGgo..."} — 直接传入 base64，仅裁切
                    "iVBORw0KGgo..."             — base64 字符串（兼容旧用法）

                groups      — 群组 (dict 或 list，自动展开)

            groups 格式 (dict 或 list)::

                {"group_id": "xxx", "group_name": "校友"}
                [{"group_id": "xxx", "group_name": "校友"}, ...]

            传入 groups 后会自动设置 contact.groupIdList、contact.groupName 以及
            顶层 groupObj，实现创建联系人同时加入群组。

            group_obj: 群组对象列表（高级用法，手动提供完整 groupObj，覆盖 groups 的自动构建）

        示例::

            # 不加群组
            client.contacts.create_contact({"name": "张三", "phone": "13800138000"})

            # 带头像（文件路径）
            client.contacts.create_contact({
                "name": "张三", "phone": "13800138000",
                "photo": "avatar.jpg",
            })

            # 带头像（base64）
            client.contacts.create_contact({
                "name": "张三", "phone": "13800138000",
                "photo": {"base64": "iVBORw0KGgo..."},
            })

            # 创建时直接加入群组
            client.contacts.create_contact({
                "name": "李四", "phone": "13900139000",
                "groups": {"group_id": "Fud_iCMH...", "group_name": "校友"},
            })
        """
        info = self._resolve_photo(info)
        contact, auto_group_obj = parse_simple_contact(info)

        url = f"{self.BASE_URL}/contact/createContact"
        body: Dict[str, Any] = {
            "contact": contact,
            "groupObj": group_obj if group_obj is not None else auto_group_obj,
        }
        data = self._post(url, body, trace_prefix="03112")
        if self._is_success(data):
            data["ok"] = True
        return data

    def update_contact(
        self,
        info: Dict[str, Any],
        *,
        group_obj: Optional[List[Dict[str, Any]]] = None,
    ) -> Result:
        """更新联系人（传入简化字典，自动解析）

        info 中必须包含 contact_id。

        Args:
            info: 简化联系人信息字典，必须含 contact_id，其余 key 同 create_contact
            group_obj: 群组对象列表（高级用法，手动提供完整 groupObj，覆盖 groups 的自动构建）

        示例::

            client.contacts.update_contact({"contact_id": "FsuGCA_...", "name": "新名字"})
            client.contacts.update_contact({
                "contact_id": "FsuGCA_...", "phone": "13900139000",
                "photo": "avatar.jpg",
                "groups": {"group_id": "Fud_iCMH...", "group_name": "校友"},
            })
        """
        info = self._resolve_photo(info)
        contact, auto_group_obj = parse_simple_contact(info)

        url = f"{self.BASE_URL}/contact/updateContact"
        body: Dict[str, Any] = {
            "contact": contact,
            "groupObj": group_obj if group_obj is not None else auto_group_obj,
            "primaryGroups": [],
        }
        data = self._post(url, body, trace_prefix="03113")
        if self._is_success(data):
            data["ok"] = True
        return data

    def delete_contacts(
        self,
        delete_contact_obj: List[Dict[str, Any]],
    ) -> Result:
        """删除联系人（移入回收站）

        Args:
            delete_contact_obj: 待删除联系人对象列表，每项含:
                - contactId: 联系人ID
                - contactUuId: 联系人UUID
                - groupIdList: 所属群组ID列表
                - groupNameList: 所属群组名称列表
        """
        url = f"{self.BASE_URL}/contact/deleteContacts"
        body: Dict[str, Any] = {"deleteContactObj": delete_contact_obj}
        data = self._post(url, body, trace_prefix="03114")
        if self._is_success(data):
            data["ok"] = True
        return data

    def delete_recyle_contacts(self, contact_ids: List[str]) -> Result:
        """永久删除回收站中的联系人

        Args:
            contact_ids: 联系人ID列表
        """
        url = f"{self.BASE_URL}/contact/deleteRecyleContacts"
        body: Dict[str, Any] = {"contactIds": contact_ids}
        data = self._post(url, body, trace_prefix="03114")
        if self._is_success(data):
            data["ok"] = True
        return data

    def resume_contacts(self, contact_id_list: List[str]) -> Result:
        """从回收站恢复联系人

        Args:
            contact_id_list: 联系人ID列表
        """
        url = f"{self.BASE_URL}/contact/resumeContacts"
        body: Dict[str, Any] = {"contactIdList": contact_id_list}
        data = self._post(url, body, trace_prefix="03110")
        if self._is_success(data):
            data["ok"] = True
        return data

    def preview_img(
        self,
        image: str,
        filename: str = "",
        *,
        crop_square: bool = True,
        square_size: int = 162,
        is_base64: bool = False,
    ) -> Result:
        """上传联系人头像图片，获取 photoUrl (Base64)

        上传后返回的 photoUrl 可直接用于 create_contact / update_contact 的 photo 字段。

        支持两种输入方式::

            # 方式1: 传入本地文件路径（默认）
            result = client.contacts.preview_img("photo.jpg")

            # 方式2: 传入已有的 Base64 字符串（跳过服务端上传，仅做裁切）
            result = client.contacts.preview_img(base64_str, is_base64=True)

        服务端返回的图片通常不是正方形，而华为云联系人头像要求正方形。
        网页端会在创建联系人前将图片居中裁切为正方形（默认 162×162）。
        设置 crop_square=True（默认）会自动执行此裁切。

        Args:
            image: 本地图片文件路径 或 Base64 编码的图片字符串
            filename: 文件名（为空则使用原文件名，仅文件路径模式有效）
            crop_square: 是否自动将图片裁切为正方形（默认 True）
            square_size: 正方形头像的像素尺寸（默认 162）
            is_base64: 为 True 时 image 参数视为 Base64 字符串，跳过服务端上传

        Returns:
            成功时返回 {"ok": True, "photoUrl": "<Base64>", ...}

        示例::

            # 文件路径方式
            result = client.contacts.preview_img("photo.jpg")
            if result.get("ok"):
                client.contacts.create_contact({
                    "name": "张三", "phone": "13800138000",
                    "photo": result["photoUrl"],
                })

            # Base64 方式（用户已有处理好的图片数据）
            result = client.contacts.preview_img(base64_str, is_base64=True)
            if result.get("ok"):
                client.contacts.create_contact({
                    "name": "张三", "phone": "13800138000",
                    "photo": result["photoUrl"],
                })
        """
        import os

        # Base64 模式：跳过上传，直接裁切
        if is_base64:
            photo_b64 = image
            if crop_square:
                photo_b64 = _crop_square_base64(photo_b64, size=square_size)
            return {"ok": True, "photoUrl": photo_b64}

        # 文件路径模式：上传到服务端
        url = f"{self.BASE_URL}/contact/previewImg"
        trace_id = _generate_traceid("03110")
        headers = self._headers()
        headers["traceid"] = trace_id
        # 移除 content-type，让 requests 自动设置 multipart boundary
        headers.pop("content-type", None)

        if not filename:
            filename = os.path.basename(image)

        with open(image, "rb") as f:
            files = {
                "avatar": (filename, f, "image/jpeg"),
            }
            try:
                resp = self._request_with_retry(
                    "POST", url, headers=headers, files=files, timeout=60, verify=False,
                )
                self._sync_cookies(resp)
                if resp.status_code == 200:
                    data = resp.json()
                    if self._is_success(data):
                        data["ok"] = True
                        # 从 data 字段提取 photoUrl
                        # 服务端返回的 data 格式: "filename|fileId|base64|size|hash"
                        raw_data = data.get("data", "")
                        if raw_data and isinstance(raw_data, str):
                            parts = raw_data.split("|")
                            if len(parts) >= 3:
                                data["fileName"] = parts[0]
                                data["fileId"] = parts[1]
                                photo_b64 = parts[2]
                                if crop_square:
                                    photo_b64 = _crop_square_base64(
                                        photo_b64, size=square_size,
                                    )
                                data["photoUrl"] = photo_b64
                                if len(parts) >= 5:
                                    data["fileSize"] = parts[3]
                                    data["fileHash"] = parts[4]
                    return data
                if resp.status_code == 401:
                    return {"ok": False, "error": "认证失败(401)，cookies 已过期", "_code": "401"}
                return {"ok": False, "error": f"HTTP {resp.status_code}", "_code": str(resp.status_code)}
            except Exception as e:
                return {"ok": False, "error": "请求异常", "detail": str(e), "_code": "-1"}

    def query_count(self) -> Result:
        """查询联系人和群组数量

        Returns:
            包含 contactCount 和 groupCount
        """
        url = f"{self.BASE_URL}/contact/queryCount"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix="03116")
        if self._is_success(data):
            data["ok"] = True
        return data

    # ---------- 群组操作 ----------

    def get_all_groups(self) -> Result:
        """获取所有联系人分组"""
        url = f"{self.BASE_URL}/contact/getAllGroups"
        trace_id = _generate_traceid("03111")
        params = {
            "traceId": trace_id,
            "currentDate": int(time.time() * 1000),
        }
        return self._post_with_params(url, {}, params=params)

    def create_group(self, group_name: str) -> Result:
        """创建联系人分组

        Args:
            group_name: 群组名称
        """
        url = f"{self.BASE_URL}/contact/createGroup"
        body: Dict[str, Any] = {"groupName": group_name}
        data = self._post(url, body, trace_prefix="03112")
        if self._is_success(data):
            data["ok"] = True
        return data

    def add_contacts_to_groups(
        self,
        group_ids: List[str],
        contact_ids: List[Dict[str, str]],
        group_obj: Optional[Dict[str, Any]] = None,
    ) -> Result:
        """添加已有联系人到群组

        也可在创建/更新联系人时通过 groups 参数直接加入群组。

        Args:
            group_ids: 目标群组ID列表
            contact_ids: 联系人列表，每项含 contactId 和 uId，例: [{"contactId": "xxx", "uId": "yyy"}]
            group_obj: 群组对象，含 groupId、groupName、contactIdList、contactUuIdList
        """
        url = f"{self.BASE_URL}/contact/addContacts2Groups"
        body: Dict[str, Any] = {
            "groupIds": group_ids,
            "contactIds": contact_ids,
        }
        if group_obj is not None:
            body["groupObj"] = group_obj
        data = self._post(url, body, trace_prefix="03113")
        if self._is_success(data):
            data["ok"] = True
        return data

    # ---------- 导入/导出 ----------

    def export_contacts(self, save_path: str = "") -> Result:
        """导出联系人（vCard 格式）

        Args:
            save_path: 保存文件路径，为空则仅返回内容不保存
        """
        url = f"{self.BASE_URL}/contact/exportContacts"
        trace_id = _generate_traceid("03115")
        params = {
            "traceId": trace_id,
            "dt": int(time.time() * 1000),
        }
        try:
            resp = self._request_with_retry(
                "GET", url, headers=self._headers(), params=params, timeout=60, verify=False,
            )
            self._sync_cookies(resp)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "json" in content_type:
                    data = resp.json()
                    code = str(data.get("code", ""))
                    if code == "402":
                        return {"ok": False, "error": "设备未认证(402)", "_code": "402"}
                    return data
                vcf_bytes = resp.content
                result: Dict[str, Any] = {
                    "ok": True,
                    "size": len(vcf_bytes),
                    "content_type": content_type,
                    "vcf_content": vcf_bytes,
                }
                if save_path:
                    with open(save_path, "wb") as f:
                        f.write(vcf_bytes)
                    result["save_path"] = save_path
                return result
            if resp.status_code == 401:
                return {"ok": False, "error": "认证失败(401)，cookies 已过期", "_code": "401"}
            if resp.status_code == 402:
                return {"ok": False, "error": "设备未认证(402)", "_code": "402"}
            return {"ok": False, "error": f"HTTP {resp.status_code}", "_code": str(resp.status_code)}
        except Exception as e:
            return {"ok": False, "error": "请求异常", "detail": str(e), "_code": "-1"}

    def import_contacts(
        self,
        vcf_data: Union[str, bytes],
        filename: str = "",
        contact_list_id: str = "",
        group_name: str = "",
    ) -> Result:
        """导入联系人（VCF 文件）

        支持两种输入方式::

            # 方式1: 直接传文件路径（推荐）
            client.contacts.import_contacts("contacts.vcf")

            # 方式2: 传入字节内容
            with open("contacts.vcf", "rb") as f:
                vcf_data = f.read()
            client.contacts.import_contacts(vcf_data, filename="contacts.vcf")

        Args:
            vcf_data: VCF 文件路径（str）或字节内容（bytes）
            filename: 文件名（为空则使用原文件名，仅字节内容模式有效）
            contact_list_id: 联系人列表ID
            group_name: 导入到的群组名称
        """
        # 如果传入的是文件路径，自动读取
        if isinstance(vcf_data, str):
            import os
            if os.path.isfile(vcf_data):
                if not filename:
                    filename = os.path.basename(vcf_data)
                with open(vcf_data, "rb") as f:
                    vcf_data = f.read()
            else:
                return {"ok": False, "error": f"文件不存在: {vcf_data}", "_code": "-1"}
        url = f"{self.BASE_URL}/contact/importContacts"
        trace_id = _generate_traceid("03115")
        url_with_params = f"{url}?traceId={trace_id}"
        headers = self._headers()
        headers["traceid"] = trace_id
        headers["content-type"] = "multipart/form-data"

        if not filename:
            filename = "contacts.vcf"

        files = {
            "doc": (filename, vcf_data, "text/x-vcard"),
        }
        data = {
            "contactListID": contact_list_id,
            "groupName": group_name,
            "contactIds": "",
            "contactUuIds": "",
        }
        try:
            resp = self._request_with_retry(
                "POST", url_with_params, headers=headers, files=files, data=data, timeout=60, verify=False,
            )
            self._sync_cookies(resp)
            if resp.status_code == 200:
                return resp.json()
            return {"ok": False, "error": f"HTTP {resp.status_code}", "_code": str(resp.status_code)}
        except Exception as e:
            return {"ok": False, "error": "请求异常", "detail": str(e), "_code": "-1"}

    # ---------- 内部工具 ----------

    def _post_with_params(
        self,
        url: str,
        body: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST 请求，同时携带 query 参数（用于 getAllGroups 等接口）"""
        if "traceId" not in body:
            body["traceId"] = _generate_traceid("03111")
        try:
            resp = self._request_with_retry(
                "POST", url, headers=self._headers(), json=body, params=params, timeout=30, verify=False,
            )
            self._sync_cookies(resp)
            if resp.status_code == 200:
                data = resp.json()
                if self._is_success(data):
                    data["ok"] = True
                return data
            if resp.status_code == 401:
                return {"ok": False, "error": "认证失败(401)，cookies 已过期", "_code": "401"}
            return {"ok": False, "error": f"HTTP {resp.status_code}", "_code": str(resp.status_code)}
        except Exception as e:
            return {"ok": False, "error": "请求异常", "detail": str(e), "_code": "-1"}
