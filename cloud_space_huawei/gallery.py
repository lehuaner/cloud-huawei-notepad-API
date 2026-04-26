"""华为云空间 · 图库模块

基于抓包数据验证的 API 接口封装。

简化用法::

    # 获取图库统计信息
    stat = client.gallery.get_stat_info()

    # 查询相册列表
    albums = client.gallery.query_albums()

    # 获取照片列表（相机相册）
    files = client.gallery.get_files(album_id="default-album-1")

    # 获取照片缩略图/下载 URL
    urls = client.gallery.get_file_urls(
        files=[{"uniqueId": "xxx", "albumId": "default-album-1"}],
        file_type="1",
    )

    # 收藏/取消收藏
    client.gallery.update_favorite(unique_id="xxx", album_id="default-album-1", favorite=True)

    # 创建自定义相册
    result = client.gallery.create_album("我的相册")

    # 删除照片（移入回收站）
    client.gallery.delete_files(
        album_id="default-album-1",
        unique_ids=["xxx", "yyy"],
    )
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

from .base import (
    BaseModule,
    LONG_TIMEOUT,
    MEDIUM_TIMEOUT,
    Result,
    TRACE_GALLERY_CREATE,
    TRACE_GALLERY_DELETE,
    TRACE_GALLERY_INFO,
    TRACE_GALLERY_LIST,
    TRACE_GALLERY_PURGE,
    TRACE_GALLERY_QUERY,
    TRACE_GALLERY_RESTORE,
    TRACE_GALLERY_UPLOAD,
    _generate_traceid,
)

logger = logging.getLogger("cloud-space-huawei.gallery")

# ============================================================
# 常量
# ============================================================

ALBUM_URL = "https://cloud.huawei.com/album"
DRIVE_PROXY_URL = "https://cloud.huawei.com/driveFileProxy"

# 预定义相册 ID
DEFAULT_ALBUM_CAMERA = "default-album-1"        # 相机
DEFAULT_ALBUM_SCREENSHOT = "default-album-2"    # 截图
DEFAULT_ALBUM_RECYCLE = "default-album-3"       # 回收站
DEFAULT_ALBUM_HIDDEN = "default-album-4"        # 隐藏

# 文件类型
FILE_TYPE_IMAGE = "1"   # 图片
FILE_TYPE_VIDEO = "9"   # 视频
FILE_TYPE_RECYCLE = "4" # 回收站（getSimpleFile 中 type=4 可查询回收站文件）
# 注意：回收站操作与手机端隔离——手机端无法看到电脑端回收站里的文件，
# 电脑端回收站列表也无法看到手机删除的照片。

# 缩略图尺寸预设
THUMB_ORIGINAL = "imgszexqu"   # 原图/大图
THUMB_CROP = "imgcropa"        # 裁切缩略图
THUMB_LCD = "imgszthm"         # LCD 缩略图

# smallThumbnails：比 LCD 缩略图更小，用于列表页预览，加载更快
# 通过 get_file_urls（getSingleUrl）返回的 url 中包含 smallThumbnails 路径时，
# 对应的就是此类缩略图，尺寸最小，适合批量加载展示。


class GalleryModule(BaseModule):
    """华为云图库

    通过 HuaweiCloudClient.gallery 访问::

        client = HuaweiCloudClient.from_cookies(cookies)
        stat = client.gallery.get_stat_info()
        albums = client.gallery.query_albums()
    """

    # ---------- 统计信息 ----------

    def get_stat_info(self, need_refresh: int = 0) -> Result:
        """获取图库统计信息

        Args:
            need_refresh: 是否刷新，0=不刷新

        Returns:
            包含 photoNum, videoNum, photoFavNum, videoFavNum 等统计信息
        """
        url = f"{ALBUM_URL}/galleryStatInfo"
        body: Dict[str, Any] = {"needRefresh": need_refresh}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_QUERY)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "图库统计" if code == "0" else f"失败({code})",
                "data": {
                    "photoNum": data.get("photoNum", 0),
                    "videoNum": data.get("videoNum", 0),
                    "photoFavNum": data.get("photoFavNum", 0),
                    "videoFavNum": data.get("videoFavNum", 0),
                    "fversion": data.get("fversion", ""),
                }}

    def get_date_stat_info(self, stat_type: int = 0) -> Result:
        """按日期统计图库文件数量

        Args:
            stat_type: 统计类型，0=全部

        Returns:
            包含 dateStatInfoList，每项含 date(YYYYMMDD), imgNum, videoNum
        """
        url = f"{ALBUM_URL}/galleryDateStatInfo"
        body: Dict[str, Any] = {"type": stat_type}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_QUERY)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        items = data.get("dateStatInfoList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"{len(items)}个日期" if code == "0" else f"失败({code})",
                "data": {"dateStatInfoList": items, "total": len(items)}}

    def get_album_stat_info(self, album_ids: List[str]) -> Result:
        """获取指定相册的统计信息

        Args:
            album_ids: 相册ID列表，如 ["default-album-1"]

        Returns:
            包含 albumStatInfoList
        """
        url = f"{ALBUM_URL}/galleryAlbumStatInfo"
        body: Dict[str, Any] = {"albumList": album_ids}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_INFO)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        items = data.get("albumStatInfoList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"{len(items)}个相册统计" if code == "0" else f"失败({code})",
                "data": {"albumStatInfoList": items}}

    def get_album_status(self) -> Result:
        """获取图库云同步状态

        Returns:
            包含 cloudVersion, status, remain, deleteTime, disableTime
        """
        trace_id = _generate_traceid(TRACE_GALLERY_INFO)
        url = f"{ALBUM_URL}/queryAlbumStatus?traceId={trace_id}"
        body: Dict[str, Any] = {"traceId": trace_id}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_INFO)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "同步状态" if code == "0" else f"失败({code})",
                "data": {
                    "cloudVersion": data.get("cloudVersion", ""),
                    "status": data.get("status", ""),
                    "remain": data.get("remain", 0),
                    "deleteTime": data.get("deleteTime", ""),
                    "disableTime": data.get("disableTime", ""),
                }}

    def get_server_time(self) -> Result:
        """获取服务器时间

        Returns:
            包含 serverTime (毫秒时间戳)
        """
        trace_id = _generate_traceid(TRACE_GALLERY_INFO)
        url = f"{ALBUM_URL}/getTime?traceId={trace_id}"
        body: Dict[str, Any] = {"traceId": trace_id}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_INFO)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "服务器时间" if code == "0" else f"失败({code})",
                "data": {"serverTime": data.get("serverTime", 0)}}

    # ---------- 相册操作 ----------

    def query_albums(self, language: str = "zh-cn") -> Result:
        """查询所有相册列表

        Args:
            language: 语言，默认 "zh-cn"

        Returns:
            包含 albumList，每项含 albumId, albumName, photoNum, videoNum, createTime 等
        """
        url = f"{ALBUM_URL}/queryAlbumInfo"
        body: Dict[str, Any] = {"isHash": False, "language": language}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_QUERY)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        albums = data.get("albumList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"{len(albums)}个相册" if code == "0" else f"失败({code})",
                "data": {"albumList": albums, "total": len(albums)}}

    def create_album(self, album_name: str, album_type: int = 3) -> Result:
        """创建自定义相册

        注意: 创建相册后如果不添加图片，该相册将不会在手机端显示，
              仅在电脑端可见为空相册。请创建后及时添加图片。

        Args:
            album_name: 相册名称
            album_type: 相册类型，3=自定义相册

        Returns:
            包含新创建的 albumId
        """
        url = f"{ALBUM_URL}/createAlbum"
        body: Dict[str, Any] = {"albumName": album_name, "albumType": album_type}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_CREATE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "创建成功" if code == "0" else f"失败({code})",
                "data": {"albumId": data.get("albumId", ""), "albumName": album_name}}

    # ---------- 文件浏览 ----------

    def get_files(
        self,
        album_id: Optional[str] = None,
        current_num: int = 0,
        count: int = 15,
        file_type: Optional[str] = None,
    ) -> Result:
        """获取相册内的文件列表

        查询回收站内容：file_type="4", album_id=None，例如::

            recycle_files = client.gallery.get_files(file_type="4")

        判断文件是否在回收站：查看返回的 recycleTime 字段，
        非空字符串（如 "1777137676295"）表示在回收站，空字符串表示不在。

        Args:
            album_id: 相册ID，None 表示全部。
                      预定义相册: "default-album-1"(相机), "default-album-2"(截图),
                      "default-album-3"(回收站), "default-album-4"(隐藏)
            current_num: 起始偏移量，0=从头开始
            count: 每页数量，默认15
            file_type: 文件类型，"1"=图片, "9"=视频, "4"=回收站, None=全部

        Returns:
            包含 fileList 和 hasMore
        """
        url = f"{ALBUM_URL}/getSimpleFile"
        body: Dict[str, Any] = {
            "albumId": album_id,
            "currentNum": current_num,
            "count": count,
            "type": file_type,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_LIST)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        # getSimpleFile 使用 resultCode
        result_code = str(data.get("resultCode", ""))
        code = str(data.get("code", result_code))
        files = data.get("fileList", [])
        has_more = data.get("hasMore", False)
        ok = code == "0" or result_code == "0"
        return {"ok": ok, "code": code,
                "msg": f"{len(files)}个文件" if ok else f"失败({code})",
                "data": {"fileList": files, "hasMore": has_more, "total": len(files)}}

    def get_file_urls(
        self,
        files: List[Dict[str, str]],
        file_type: str = FILE_TYPE_IMAGE,
        thumb_type: str = THUMB_ORIGINAL,
        thumb_height: int = 350,
        thumb_width: int = 350,
    ) -> Result:
        """获取文件的缩略图/下载 URL

        注意：返回的 url 中可能包含 smallThumbnails 路径（如
        /v2/cloudPhoto/callback/v1/smallThumbnails/...），这是比 LCD 缩略图
        更小的缩略图，用于列表页预览，尺寸最小，加载最快。

        Args:
            files: 文件列表，每项含 uniqueId 和 albumId，例:
                   [{"uniqueId": "xxx", "albumId": "default-album-1"}]
            file_type: 文件类型，"1"=图片, "9"=视频
            thumb_type: 缩略图类型，"imgszexqu"=原图, "imgcropa"=裁切
            thumb_height: 缩略图高度
            thumb_width: 缩略图宽度

        Returns:
            包含 urlList，每项含 url, fileName, fileType, sha256 等
        """
        url = f"{ALBUM_URL}/getSingleUrl"
        body: Dict[str, Any] = {
            "fileList": files,
            "type": file_type,
            "thumbType": thumb_type,
            "thumbHeight": thumb_height,
            "thumbWidth": thumb_width,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_INFO)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        url_list = data.get("urlList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"{len(url_list)}个URL" if code == "0" else f"失败({code})",
                "data": {"urlList": url_list}}

    def get_cover_files(
        self,
        album_ids: List[str],
        thumb_height: int = 40,
        thumb_width: int = 40,
        thumb_type: str = THUMB_CROP,
    ) -> Result:
        """获取相册封面文件

        Args:
            album_ids: 相册ID列表
            thumb_height: 缩略图高度，默认40
            thumb_width: 缩略图宽度，默认40
            thumb_type: 缩略图类型，默认裁切

        Returns:
            包含 fileList，格式为 {userId: {albumId: fileData}}
        """
        url = f"{ALBUM_URL}/getCoverFiles"
        body: Dict[str, Any] = {
            "albumIdList": album_ids,
            "thumbHeight": thumb_height,
            "thumbWidth": thumb_width,
            "thumbType": thumb_type,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_INFO)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        file_list = data.get("fileList", {})
        return {"ok": code == "0", "code": code,
                "msg": "封面文件" if code == "0" else f"失败({code})",
                "data": {"fileList": file_list}}

    def get_thumb_lcd_url(
        self,
        files: List[Dict[str, str]],
        file_type: str = FILE_TYPE_IMAGE,
        thumb_type: str = THUMB_LCD,
        thumb_height: int = 120,
        thumb_width: int = 120,
    ) -> Result:
        """获取文件的 LCD 缩略图 URL（含分辨率和旋转信息）

        Args:
            files: 文件列表，每项含 uniqueId 和 albumId
            file_type: 文件类型，"1"=图片, "9"=视频
            thumb_type: 缩略图类型
            thumb_height: 缩略图高度
            thumb_width: 缩略图宽度

        Returns:
            包含 successList，每项含 fileUrl, fileName, size, sha256, expand(含resolution/rotate)
        """
        url = f"{ALBUM_URL}/getThumbLcdUrl"
        body: Dict[str, Any] = {
            "lcd": {
                "type": file_type,
                "thumbType": thumb_type,
                "thumbHeight": thumb_height,
                "thumbWidth": thumb_width,
            },
            "fileList": files,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_INFO)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        success_list = data.get("successList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"{len(success_list)}个缩略图" if code == "0" else f"失败({code})",
                "data": {"successList": success_list}}

    def get_file_detail(
        self,
        files: List[Dict[str, str]],
        owner_id: Optional[str] = None,
    ) -> Result:
        """获取文件详细信息（文件名、URL、大小、sha256等）

        Args:
            files: 文件列表，每项含 albumId 和 uniqueId
            owner_id: 所有者ID，None 表示自己

        Returns:
            包含 fileList，每项含 fileName, fileType, fileUrl, size, sha256, favorite, createTime
        """
        url = f"{ALBUM_URL}/queryCloudFileName"
        body: Dict[str, Any] = {
            "fileList": files,
            "ownerId": owner_id,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_INFO)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        file_list = data.get("fileList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"{len(file_list)}个文件详情" if code == "0" else f"失败({code})",
                "data": {"fileList": file_list}}

    # ---------- 文件操作 ----------

    def delete_files(
        self,
        album_id: str,
        unique_ids: List[str],
        recycle: str = "1",
    ) -> Result:
        """删除文件（移入回收站）

        Args:
            album_id: 相册ID
            unique_ids: 文件 uniqueId 列表
            recycle: "1"=移入回收站

        Returns:
            包含 successList 和 failList
        """
        url = f"{ALBUM_URL}/deleteAlbumFile"
        body: Dict[str, Any] = {
            "albumId": album_id,
            "recycle": recycle,
            "hash": [""],
            "uniqueId": unique_ids,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_DELETE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        success = data.get("successList", [])
        fail = data.get("failList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"成功{len(success)}个, 失败{len(fail)}个" if code == "0" else f"失败({code})",
                "data": {"successList": success, "failList": fail}}

    def move_files(
        self,
        album_id: str,
        unique_ids: List[str],
        dest_album_id: str,
        source_path: str = "",
    ) -> Result:
        """移动文件到其他相册

        Args:
            album_id: 源相册ID
            unique_ids: 文件 uniqueId 列表
            dest_album_id: 目标相册ID
            source_path: 源路径

        Returns:
            包含 successList 和 failList
        """
        url = f"{ALBUM_URL}/moveAlbumFile"
        body: Dict[str, Any] = {
            "albumId": album_id,
            "uniqueId": unique_ids,
            "destAlbumId": dest_album_id,
            "sourcePath": source_path,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_CREATE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        success = data.get("successList", [])
        fail = data.get("failList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"成功{len(success)}个, 失败{len(fail)}个" if code == "0" else f"失败({code})",
                "data": {"successList": success, "failList": fail}}

    def update_favorite(
        self,
        unique_id: str,
        album_id: str,
        favorite: bool = True,
    ) -> Result:
        """收藏/取消收藏文件

        注意：此接口为电脑端（Web）的收藏接口，与手机端的收藏机制不同。
        通过此接口收藏的图片仅在电脑端可见，不会同步到手机端收藏列表。

        Args:
            unique_id: 文件 uniqueId
            album_id: 相册ID
            favorite: True=收藏, False=取消收藏

        Returns:
            操作结果
        """
        url = f"{ALBUM_URL}/updateFavorite"
        body: Dict[str, Any] = {
            "uniqueId": unique_id,
            "albumId": album_id,
            "favorite": favorite,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_CREATE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        action = "收藏" if favorite else "取消收藏"
        return {"ok": code == "0", "code": code,
                "msg": f"{action}成功" if code == "0" else f"{action}失败({code})",
                "data": {}}

    # ---------- 回收站 ----------

    def restore_files(self, unique_ids: List[str]) -> Result:
        """从回收站恢复文件

        Args:
            unique_ids: 文件 uniqueId 列表

        Returns:
            包含 successList 和 failList
        """
        url = f"{ALBUM_URL}/restoreRecycleFiles"
        body: Dict[str, Any] = {"uniqueId": unique_ids}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_RESTORE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        success = data.get("successList", [])
        fail = data.get("failList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"恢复{len(success)}个, 失败{len(fail)}个" if code == "0" else f"失败({code})",
                "data": {"successList": success, "failList": fail}}

    def delete_recycle_files(
        self,
        album_id: str,
        unique_ids: List[str],
    ) -> Result:
        """永久删除回收站中的文件

        Args:
            album_id: 相册ID
            unique_ids: 文件 uniqueId 列表

        Returns:
            包含 successList 和 failList
        """
        url = f"{ALBUM_URL}/deleteRecycleFiles"
        body: Dict[str, Any] = {
            "albumId": album_id,
            "recycle": "1",
            "hash": [""],
            "uniqueId": unique_ids,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_PURGE)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        success = data.get("successList", [])
        fail = data.get("failList", [])
        return {"ok": code == "0", "code": code,
                "msg": f"删除{len(success)}个, 失败{len(fail)}个" if code == "0" else f"失败({code})",
                "data": {"successList": success, "failList": fail}}

    # ---------- 分享 ----------

    def query_share(self, resource: str = "album", flag: int = 3) -> Result:
        """查询分享列表

        同时调用 queryShare 和 queryGroupShare（当 v2Flag=True 时），
        合并返回完整的分享信息。

        Args:
            resource: 资源类型，默认 "album"
            flag: 标志位，默认 3

        Returns:
            包含 ownShareList, ownGroupShareList, recShareList, recGroupShareList
        """
        # 1. 调用 queryShare
        url = f"{ALBUM_URL}/queryShare"
        trace_id = _generate_traceid(TRACE_GALLERY_QUERY)
        body: Dict[str, Any] = {
            "resource": resource,
            "flag": flag,
            "traceId": trace_id,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_QUERY)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        if code != "0":
            return {"ok": False, "code": code,
                    "msg": f"失败({code})", "data": {}}

        own_share_list = data.get("ownShareList", [])
        rec_share_list = data.get("recShareList", [])
        v2_flag = data.get("v2Flag", False)

        # 2. 当 v2Flag=True 时，调用 queryGroupShare 获取群组分享
        own_group_share_list: List[Any] = []
        rec_group_share_list: List[Any] = []
        if v2_flag:
            group_result = self._query_group_share()
            if group_result.get("ok"):
                own_group_share_list = group_result["data"].get("ownGroupShareList", [])
                rec_group_share_list = group_result["data"].get("recGroupShareList", [])

        total = (len(own_share_list) + len(own_group_share_list)
                 + len(rec_share_list) + len(rec_group_share_list))
        return {"ok": True, "code": code,
                "msg": f"分享列表({total}条)" if total else "分享列表(空)",
                "data": {
                    "ownShareList": own_share_list,
                    "ownGroupShareList": own_group_share_list,
                    "recShareList": rec_share_list,
                    "recGroupShareList": rec_group_share_list,
                    "v2Flag": v2_flag,
                }}

    def _query_group_share(self) -> Result:
        """查询群组分享列表（内部方法，由 query_share 调用）

        Returns:
            包含 ownGroupShareList, recGroupShareList
        """
        trace_id = _generate_traceid(TRACE_GALLERY_QUERY)
        url = f"{ALBUM_URL}/queryGroupShare?traceId={trace_id}"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_QUERY)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "群组分享" if code == "0" else f"失败({code})",
                "data": {
                    "ownGroupShareList": data.get("ownGroupShareList", []),
                    "recGroupShareList": data.get("recGroupShareList", []),
                }}

    # ---------- 上传 ----------

    def upload_file(
        self,
        file_path: str,
        album_id: str = DEFAULT_ALBUM_CAMERA,
        file_type: str = FILE_TYPE_IMAGE,
        source_path: str = "",
    ) -> Result:
        """上传图片/视频到图库（完整流程）

        基于 uploadType=content 协议，抓包验证的上传流程::

            1. preUploadAlbumProcess（获取 lock）
            2. preUploadAlbumProcess（生成签名）
            3. POST multipart/form-data 一次上传文件（带 x-hw-signature + x-hw-properties）
            4. createAlbumFile
            5. afterUploadAlbumProcess

        Args:
            file_path: 本地文件路径
            album_id: 目标相册ID，默认相机相册
            file_type: 文件类型，"1"=图片, "9"=视频
            source_path: 来源路径（模拟手机路径）

        Returns:
            上传结果，包含 fileName, uniqueId, thumbUrl 等
        """
        if not os.path.isfile(file_path):
            return {"ok": False, "code": "-1", "msg": f"文件不存在: {file_path}"}

        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_hash = self._compute_md5(file_path)
        content_type = "image/jpeg" if file_type == FILE_TYPE_IMAGE else "video/mp4"

        # 整个上传流程使用同一个 trace_id
        upload_trace_id = _generate_traceid(TRACE_GALLERY_UPLOAD)

        # Step 1a: preUploadAlbumProcess — 获取 lock
        pre1 = self._pre_upload_album_process(
            need_to_sign_url="", http_method="POST",
            generate_sign_flag=False, first_upload_file_flag=True,
            trace_id=upload_trace_id,
        )
        if not pre1.get("ok"):
            return pre1
        cloud_lock = pre1["data"].get("cloudPhotoUserLock", "")

        # Step 1b: preUploadAlbumProcess — 生成签名
        sign_url = "/proxy/v1/upload/%2Fv2%2FcloudPhoto%2Fmedia?uploadType=content&fields=*"
        pre2 = self._pre_upload_album_process(
            need_to_sign_url=sign_url, http_method="POST",
            generate_sign_flag=True, first_upload_file_flag=False,
            trace_id=upload_trace_id,
        )
        if not pre2.get("ok"):
            return pre2
        signature = pre2["data"].get("sign", "")
        request_time_stamp = pre2["data"].get("requestTimeStamp", "")

        # Step 2: POST multipart/form-data 一次上传文件
        upload_result = self._upload_file_content(
            file_path=file_path,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            file_hash=file_hash,
            album_id=album_id,
            source_path=source_path,
            content_type=content_type,
            cloud_lock=cloud_lock,
            signature=signature,
            time_stamp=request_time_stamp,
            trace_id=upload_trace_id,
        )
        if not upload_result.get("ok"):
            return upload_result

        file_id = upload_result["data"].get("fileId", "")

        # Step 3: createAlbumFile
        now_ms = int(time.time() * 1000)
        create_file_result = self._create_album_file(
            file_id=file_id,
            album_id=album_id,
            filename=filename,
            file_type=content_type,
            create_time=now_ms,
            trace_id=upload_trace_id,
        )

        # Step 4: afterUploadAlbumProcess
        self._after_upload_album_process()

        return create_file_result

    def _pre_upload_album_process(
        self,
        need_to_sign_url: str = "",
        http_method: str = "POST",
        generate_sign_flag: bool = False,
        first_upload_file_flag: bool = False,
        trace_id: str = "",
    ) -> Result:
        """图库上传预处理

        在上传过程中被调用 3 次：
        1. firstUploadFileFlag=True, generateSignFlag=False → 获取 cloudPhotoUserLock
        2. needToSignUrl=上传路径, generateSignFlag=True → 获取 sign 和 requestTimeStamp
        3. httpMethod="PUT", generateSignFlag=False → PUT 前刷新 lock
        """
        url = f"{DRIVE_PROXY_URL}/preUploadAlbumProcess"
        body: Dict[str, Any] = {
            "needToSignUrl": need_to_sign_url,
            "httpMethod": http_method,
            "generateSignFlag": generate_sign_flag,
            "firstUploadFileFlag": first_upload_file_flag,
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_UPLOAD)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "上传预处理成功" if code == "0" else f"失败({code})",
                "data": data}

    def _upload_file_content(
        self,
        file_path: str,
        filename: str,
        file_type: str,
        file_size: int,
        file_hash: str,
        album_id: str,
        source_path: str,
        content_type: str,
        cloud_lock: str,
        signature: str = "",
        time_stamp: str = "",
        trace_id: str = "",
    ) -> Result:
        """POST multipart/form-data 一次上传文件（uploadType=content）

        抓包验证的上传方式：
        - URL 使用 uploadType=content
        - 文件通过 multipart/form-data 发送
        - 元数据通过 x-hw-properties header 传递（URL 编码的键值对）
        - 服务器直接返回文件信息（含 fileId）
        """
        from datetime import datetime, timezone
        from urllib.parse import quote

        ts = time_stamp or str(int(time.time() * 1000))
        upload_url = (
            f"https://cloud.huawei.com/proxy/v1/upload/"
            f"%2Fv2%2FcloudPhoto%2Fmedia"
            f"?uploadType=content&fields=*&timeStamp={ts}"
        )

        # createdTime 使用 ISO 格式
        now_ms = int(time.time() * 1000)
        created_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
                       f"{now_ms % 1000:03d}Z"

        # sourcePath 默认值
        src_path = source_path or f"/storage/emulated/0/Pictures/{filename}"

        # 构建 x-hw-properties header（URL 编码键值对）
        hw_properties = (
            f"albumId={quote(album_id, safe='')}"
            f"&fileType={file_type}"
            f"&createdTime={quote(created_time, safe='')}"
            f"&hash={file_hash}"
            f"&fileName={quote(filename, safe='')}"
            f"&sourcePath={quote(src_path, safe='')}"
            f"&mimeType={quote(content_type, safe='')}"
        )

        extra_headers = {
            "x-hw-lock": cloud_lock,
            "x-upload-content-length": str(file_size),
            "x-upload-content-type": content_type,
            "x-hw-app-version": "160200300",
            "x-hw-properties": hw_properties,
            "content-range": f"bytes 0-{file_size - 1}/{file_size}",
        }
        if signature:
            extra_headers["x-hw-signature"] = signature

        # 构建 multipart/form-data（文件内容一次性读取用于 multipart 构造）
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
        except OSError as e:
            return {"ok": False, "code": "-1", "msg": f"读取文件失败: {e}"}

        # 警告：multipart body 需预构造在内存中，无法真正流式上传
        # 文件读取已在 _compute_md5 中使用分块，小文件无额外内存问题

        # 手动构建 multipart body
        boundary = "----PythonFormBoundary" + hashlib.md5(
            f"{time.time()}{filename}".encode()
        ).hexdigest()[:16]
        body_parts = []
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
        )
        body_parts.append(f"Content-Type: {content_type}\r\n".encode())
        body_parts.append(b"\r\n")
        body_parts.append(file_data)
        body_parts.append(f"\r\n--{boundary}--\r\n".encode())
        multipart_body = b"".join(body_parts)

        extra_headers["content-type"] = f"multipart/form-data; boundary={boundary}"

        try:
            headers = self._headers()
            if not trace_id:
                trace_id = _generate_traceid(TRACE_GALLERY_UPLOAD)
            headers["x-hw-trace-id"] = trace_id
            headers.update(extra_headers)

            resp = self._request_with_retry(
                "POST", upload_url,
                headers=headers, data=multipart_body,
                timeout=LONG_TIMEOUT, verify=False,
            )
            self._sync_cookies(resp)

            if resp.status_code == 200:
                data = resp.json()
                file_id = data.get("id", "")
                return {"ok": True, "code": "0",
                        "msg": "文件上传成功",
                        "data": {**data, "fileId": file_id}}
            try:
                err_data = resp.json()
                err_msg = ""
                if "error" in err_data:
                    errors = err_data["error"].get("errorDetail", [])
                    if errors:
                        err_msg = errors[0].get("description", str(err_data))
                    else:
                        err_msg = str(err_data["error"])
                return {"ok": False, "code": str(resp.status_code),
                        "msg": f"文件上传失败: {err_msg or resp.text[:200]}"}
            except Exception:
                return {"ok": False, "code": str(resp.status_code),
                        "msg": f"文件上传失败 HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"文件上传异常: {e}"}

    def _after_upload_album_process(self) -> Result:
        """图库上传后处理"""
        url = f"{DRIVE_PROXY_URL}/afterUploadAlbumProcess"
        body: Dict[str, Any] = {}
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_INFO)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "上传后处理成功" if code == "0" else f"失败({code})",
                "data": data}

    def _create_album_file(
        self,
        file_id: str,
        album_id: str,
        filename: str,
        file_type: str,
        create_time: int,
        trace_id: str = "",
    ) -> Result:
        """创建相册文件记录

        Args:
            file_type: MIME 类型字符串，如 "image/jpeg" 或 "video/mp4"
            create_time: 毫秒时间戳
            trace_id: 跟踪ID
        """
        url = f"{ALBUM_URL}/createAlbumFile"
        body: Dict[str, Any] = {
            "fileInfo": {
                "fileId": file_id,
                "albumId": album_id,
                "fileName": filename,
                "fileType": file_type,  # MIME 类型字符串
                "createTime": create_time,
            },
            "traceId": trace_id or _generate_traceid(TRACE_GALLERY_UPLOAD),
        }
        data = self._post(url, body, trace_prefix=TRACE_GALLERY_UPLOAD)
        if "error" in data:
            return {"ok": False, "code": data.get("_code", "-1"), "msg": data["error"]}
        code = str(data.get("code", ""))
        return {"ok": code == "0", "code": code,
                "msg": "上传完成" if code == "0" else f"失败({code})",
                "data": {
                    "fileName": data.get("fileName", filename),
                    "uniqueId": data.get("uniqueId", ""),
                    "thumbUrl": data.get("thumbUrl", ""),
                    "sdsctime": data.get("sdsctime", ""),
                }}

    # ---------- 下载 ----------

    def download_file(
        self,
        file_url: str,
        save_path: str,
    ) -> Result:
        """下载图库文件（底层方法，直接通过 URL 下载）

        Args:
            file_url: 文件 URL（从 get_file_urls / get_file_detail 获取）
            save_path: 保存路径（含文件名）

        Returns:
            下载结果，包含保存路径和文件大小
        """
        try:
            resp = self._request_with_retry(
                "GET", file_url, headers=self._headers(), timeout=MEDIUM_TIMEOUT, verify=False,
            )
            self._sync_cookies(resp)
            if resp.status_code == 200:
                os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                return {"ok": True, "code": "0", "msg": "下载成功",
                        "data": {"path": save_path, "size": len(resp.content)}}
            return {"ok": False, "code": str(resp.status_code),
                    "msg": f"下载失败 HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "code": "-1", "msg": f"下载异常: {e}"}

    def download_photo(
        self,
        unique_id: str,
        album_id: str,
        save_dir: str = ".",
        owner_id: Optional[str] = None,
    ) -> Result:
        """下载图库原图（便捷方法，自动获取文件名和下载 URL）

        流程: queryCloudFileName → 获取 fileUrl/fileName → GET 下载

        Args:
            unique_id: 文件 uniqueId
            album_id: 相册ID
            save_dir: 保存目录，默认当前目录
            owner_id: 所有者ID，None 表示自己

        Returns:
            下载结果，包含保存路径、文件名和文件大小
        """
        # 1. 获取文件详情（含下载URL和文件名）
        detail = self.get_file_detail(
            files=[{"albumId": album_id, "uniqueId": unique_id}],
            owner_id=owner_id,
        )
        if not detail.get("ok"):
            return detail

        file_list = detail.get("data", {}).get("fileList", [])
        if not file_list:
            return {"ok": False, "code": "-1", "msg": "未找到文件信息"}

        file_info = file_list[0]
        file_url = file_info.get("fileUrl", "")
        file_name = file_info.get("fileName", "")

        if not file_url:
            return {"ok": False, "code": "-1", "msg": "未获取到下载URL"}

        if not file_name:
            # 从 URL 或 uniqueId 推断文件名
            file_name = f"{unique_id[:16]}"

        # 2. 下载文件
        save_path = os.path.join(save_dir, file_name)
        return self.download_file(file_url, save_path)

    def download_photos_batch(
        self,
        files: List[Dict[str, str]],
        save_dir: str = ".",
        owner_id: Optional[str] = None,
    ) -> Result:
        """批量下载图库原图

        Args:
            files: 文件列表，每项含 uniqueId 和 albumId
            save_dir: 保存目录
            owner_id: 所有者ID，None 表示自己

        Returns:
            批量下载结果，包含成功/失败列表
        """
        success_list: List[Dict[str, Any]] = []
        fail_list: List[Dict[str, Any]] = []

        for f in files:
            uid = f.get("uniqueId", "")
            aid = f.get("albumId", "")
            if not uid or not aid:
                fail_list.append({"uniqueId": uid, "albumId": aid, "reason": "参数不完整"})
                continue
            result = self.download_photo(
                unique_id=uid, album_id=aid,
                save_dir=save_dir, owner_id=owner_id,
            )
            if result.get("ok"):
                success_list.append({
                    "uniqueId": uid,
                    "path": result["data"].get("path", ""),
                    "size": result["data"].get("size", 0),
                })
            else:
                fail_list.append({"uniqueId": uid, "reason": result.get("msg", "未知错误")})

        total = len(success_list) + len(fail_list)
        return {"ok": True, "code": "0",
                "msg": f"下载完成: 成功{len(success_list)}/{total}",
                "data": {"successList": success_list, "failList": fail_list}}

    # ---------- 工具方法 ----------

    @staticmethod
    def _compute_md5(file_path: str, chunk_size: int = 8192) -> str:
        """计算文件的 MD5 哈希值"""
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
