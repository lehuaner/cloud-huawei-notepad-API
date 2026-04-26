"""
Cloud Space API — Cloud Space Python SDK

提供登录、备忘录、联系人、图库、云盘、查找设备等接口。

快速上手:
    from cloud_space_huawei import HuaweiCloudClient

    # 方式1: 账号密码登录
    client = HuaweiCloudClient()
    result = client.login("手机号", "密码")
    if result.need_verify:
        code = input("验证码: ")
        result = client.verify_device(code)
    # 保存 cookies，下次直接用 cookies 登录即可跳过设备验证
    cookies = result.cookies

    # 方式2: 从 cookies 恢复会话
    client = HuaweiCloudClient.from_cookies(cookies)
    notes = client.notepad.get_notes_list()

    # 方式3: 账号密码登录 + 传入已有 cookies（跳过设备验证）
    result = client.login("手机号", "密码", cookies=saved_cookies)
"""

from .client import HuaweiCloudClient
from .auth import LoginResult
from .contacts import (
    parse_simple_contact,
    TEL_TYPES, TEL_TYPE_MAX,
    EMAIL_TYPES, EMAIL_TYPE_MAX,
    IM_TYPES, IM_TYPE_MAX,
    ADDRESS_TYPES, ADDRESS_TYPE_MAX,
    DATE_TYPES, DATE_TYPE_MAX,
    URL_TYPE_MAX,
    RELATION_TYPES, RELATION_TYPE_MAX,
    EVENT_TYPES, EVENT_TYPE_MAX,
)
from .gallery import (
    GalleryModule,
    DEFAULT_ALBUM_CAMERA,
    DEFAULT_ALBUM_SCREENSHOT,
    DEFAULT_ALBUM_RECYCLE,
    DEFAULT_ALBUM_HIDDEN,
    FILE_TYPE_IMAGE,
    FILE_TYPE_VIDEO,
    FILE_TYPE_RECYCLE,
    THUMB_ORIGINAL,
    THUMB_CROP,
    THUMB_LCD,
)
from .drive import DriveModule
from .payment import PaymentModule
from .revisions import RevisionsModule

__all__ = [
    "HuaweiCloudClient",
    "LoginResult",
    "parse_simple_contact",
    "TEL_TYPES", "TEL_TYPE_MAX",
    "EMAIL_TYPES", "EMAIL_TYPE_MAX",
    "IM_TYPES", "IM_TYPE_MAX",
    "ADDRESS_TYPES", "ADDRESS_TYPE_MAX",
    "DATE_TYPES", "DATE_TYPE_MAX",
    "URL_TYPE_MAX",
    "RELATION_TYPES", "RELATION_TYPE_MAX",
    "EVENT_TYPES", "EVENT_TYPE_MAX",
    "GalleryModule",
    "DEFAULT_ALBUM_CAMERA",
    "DEFAULT_ALBUM_SCREENSHOT",
    "DEFAULT_ALBUM_RECYCLE",
    "DEFAULT_ALBUM_HIDDEN",
    "FILE_TYPE_IMAGE",
    "FILE_TYPE_VIDEO",
    "FILE_TYPE_RECYCLE",
    "THUMB_ORIGINAL",
    "THUMB_CROP",
    "THUMB_LCD",
    "DriveModule",
    "PaymentModule",
    "RevisionsModule",
]
__version__ = "0.3.0"
