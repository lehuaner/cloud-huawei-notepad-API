# 华为云空间 · 图库模块使用文档

## 概述

图库模块 (`GalleryModule`) 封装了华为云空间 Web 端全部图库 API，支持图库统计查询、相册管理、文件浏览与操作、回收站管理、分享查询、上传与下载等功能。

通过 `client.gallery` 访问：

```python
from cloud_space_huawei import HuaweiCloudClient

client = HuaweiCloudClient.from_cookies(cookies: dict)
```

---

## 返回格式

所有方法返回 `dict`，成功时包含 `"ok": True`：

```python
{
    "ok": True,          # 操作是否成功
    "code": "0",         # 状态码
    "msg": "3个文件",     # 结果描述
    "data": ...          # 具体数据（视接口而定）
}
```

失败时：

```python
{
    "ok": False,
    "code": "-1",
    "msg": "错误描述"
}
```

---

## 常量预定义

### 预定义相册 ID

| 常量 | 值 | 说明 |
|------|-----|------|
| `DEFAULT_ALBUM_CAMERA` | `"default-album-1"` | 相机相册 |
| `DEFAULT_ALBUM_SCREENSHOT` | `"default-album-2"` | 截图相册 |
| `DEFAULT_ALBUM_RECYCLE` | `"default-album-3"` | 回收站 |
| `DEFAULT_ALBUM_HIDDEN` | `"default-album-4"` | 隐藏相册 |

### 文件类型

| 常量 | 值 | 说明 |
|------|-----|------|
| `FILE_TYPE_IMAGE` | `"1"` | 图片 |
| `FILE_TYPE_VIDEO` | `"9"` | 视频 |
| `FILE_TYPE_RECYCLE` | `"4"` | 回收站（getSimpleFile 中 type=4 可查询回收站文件） |

> **注意**：回收站操作与手机端隔离——手机端无法看到电脑端回收站里的文件，电脑端回收站列表也无法看到手机删除的照片。

### 缩略图尺寸预设

| 常量 | 值 | 说明 |
|------|-----|------|
| `THUMB_ORIGINAL` | `"imgszexqu"` | 原图/大图 |
| `THUMB_CROP` | `"imgcropa"` | 裁切缩略图 |
| `THUMB_LCD` | `"imgszthm"` | LCD 缩略图 |

> `smallThumbnails`：比 LCD 缩略图更小，用于列表页预览，加载更快。通过 `get_file_urls`（getSingleUrl）返回的 URL 中包含 `smallThumbnails` 路径时，对应的就是此类缩略图，尺寸最小，适合批量加载展示。

---

## 一、统计信息

### 1.1 获取图库统计信息 `get_stat_info()`

获取图库中照片和视频的数量统计。

```python
result = client.gallery.get_stat_info()

if result.get("ok"):
    data = result["data"]
    print(f"照片: {data['photoNum']}, 视频: {data['videoNum']}")
    print(f"收藏照片: {data['photoFavNum']}, 收藏视频: {data['videoFavNum']}")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `need_refresh` | `int` | `0` | 是否刷新，`0` = 不刷新 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `photoNum` | `int` | 照片数量 |
| `videoNum` | `int` | 视频数量 |
| `photoFavNum` | `int` | 收藏的照片数量 |
| `videoFavNum` | `int` | 收藏的视频数量 |
| `fversion` | `str` | 版本号 |

---

### 1.2 按日期统计 `get_date_stat_info()`

按日期统计图库文件数量。

```python
result = client.gallery.get_date_stat_info()

if result.get("ok"):
    for item in result["data"]["dateStatInfoList"]:
        print(f"日期: {item['date']}, 图片: {item['imgNum']}, 视频: {item['videoNum']}")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `stat_type` | `int` | `0` | 统计类型，`0` = 全部 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `dateStatInfoList` | `List` | 日期统计列表，每项含 `date`(YYYYMMDD)、`imgNum`、`videoNum` |
| `total` | `int` | 日期总数 |

---

### 1.3 获取相册统计信息 `get_album_stat_info()`

获取指定相册的统计信息。

```python
result = client.gallery.get_album_stat_info(
    album_ids=["default-album-1", "default-album-2"]
)
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `album_ids` | `List[str]` | 是 | 相册ID列表 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `albumStatInfoList` | `List` | 相册统计列表 |

---

### 1.4 获取图库云同步状态 `get_album_status()`

获取图库云同步状态信息。

```python
result = client.gallery.get_album_status()

if result.get("ok"):
    data = result["data"]
    print(f"云版本: {data['cloudVersion']}, 状态: {data['status']}")
```

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `cloudVersion` | `str` | 云版本 |
| `status` | `str` | 同步状态 |
| `remain` | `int` | 剩余数量 |
| `deleteTime` | `str` | 删除时间 |
| `disableTime` | `str` | 禁用时间 |

---

### 1.5 获取服务器时间 `get_server_time()`

获取服务器时间。

```python
result = client.gallery.get_server_time()

if result.get("ok"):
    server_time_ms = result["data"]["serverTime"]
    print(f"服务器时间: {server_time_ms}")
```

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `serverTime` | `int` | 服务器时间（毫秒时间戳） |

---

## 二、相册操作

### 2.1 查询相册列表 `query_albums()`

查询所有相册列表。

```python
result = client.gallery.query_albums()

if result.get("ok"):
    for album in result["data"]["albumList"]:
        print(f"相册: {album['albumName']}, 照片: {album.get('photoNum', 0)}, 视频: {album.get('videoNum', 0)}")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `language` | `str` | `"zh-cn"` | 语言 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `albumList` | `List` | 相册列表，每项含 `albumId`、`albumName`、`photoNum`、`videoNum`、`createTime` 等 |
| `total` | `int` | 相册总数 |

---

### 2.2 创建自定义相册 `create_album()`

创建自定义相册。

```python
result = client.gallery.create_album("我的相册")

if result.get("ok"):
    album_id = result["data"]["albumId"]
    print(f"相册创建成功，ID: {album_id}")
```

> **注意**：创建相册后如果不添加图片，该相册将不会在手机端显示，仅在电脑端可见为空相册。请创建后及时添加图片。

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `album_name` | `str` | 是 | — | 相册名称 |
| `album_type` | `int` | 否 | `3` | 相册类型，`3` = 自定义相册 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `albumId` | `str` | 新创建的相册ID |
| `albumName` | `str` | 相册名称 |

---

## 三、文件浏览

### 3.1 获取文件列表 `get_files()`

获取相册内的文件列表（分页）。

```python
# 获取相机相册中的文件
result = client.gallery.get_files(album_id="default-album-1")

# 分页查询
result = client.gallery.get_files(album_id="default-album-1", current_num=15, count=30)

# 仅查看图片
result = client.gallery.get_files(album_id="default-album-1", file_type="1")

# 仅查看视频
result = client.gallery.get_files(album_id="default-album-1", file_type="9")

# 查询回收站内容
result = client.gallery.get_files(file_type="4")
```

> 判断文件是否在回收站：查看返回的 `recycleTime` 字段，非空字符串（如 `"1777137676295"`）表示在回收站，空字符串表示不在。

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `album_id` | `Optional[str]` | `None` | 相册ID，`None` 表示全部。预定义相册：`"default-album-1"`(相机)、`"default-album-2"`(截图)、`"default-album-3"`(回收站)、`"default-album-4"`(隐藏) |
| `current_num` | `int` | `0` | 起始偏移量，`0` = 从头开始 |
| `count` | `int` | `15` | 每页数量 |
| `file_type` | `Optional[str]` | `None` | 文件类型，`"1"` = 图片、`"9"` = 视频、`"4"` = 回收站、`None` = 全部 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `fileList` | `List` | 文件列表 |
| `hasMore` | `bool` | 是否还有更多文件 |
| `total` | `int` | 本页文件数量 |

---

### 3.2 获取文件缩略图/下载 URL `get_file_urls()`

获取文件的缩略图或下载 URL。

```python
# 获取原图下载 URL
result = client.gallery.get_file_urls(
    files=[{"uniqueId": "xxx", "albumId": "default-album-1"}],
    file_type="1",
)

# 获取裁切缩略图
result = client.gallery.get_file_urls(
    files=[{"uniqueId": "xxx", "albumId": "default-album-1"}],
    file_type="1",
    thumb_type="imgcropa",
    thumb_height=200,
    thumb_width=200,
)

if result.get("ok"):
    for item in result["data"]["urlList"]:
        print(f"文件: {item['fileName']}, URL: {item['url']}")
```

> 返回的 URL 中可能包含 `smallThumbnails` 路径，这是比 LCD 缩略图更小的缩略图，用于列表页预览，尺寸最小，加载最快。

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `files` | `List[Dict[str, str]]` | — | 文件列表，每项含 `uniqueId` 和 `albumId`，如 `[{"uniqueId": "xxx", "albumId": "default-album-1"}]` |
| `file_type` | `str` | `"1"` | 文件类型，`"1"` = 图片、`"9"` = 视频 |
| `thumb_type` | `str` | `"imgszexqu"` | 缩略图类型，`"imgszexqu"` = 原图、`"imgcropa"` = 裁切 |
| `thumb_height` | `int` | `350` | 缩略图高度 |
| `thumb_width` | `int` | `350` | 缩略图宽度 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `urlList` | `List` | URL 列表，每项含 `url`、`fileName`、`fileType`、`sha256` 等 |

---

### 3.3 获取相册封面文件 `get_cover_files()`

获取相册封面文件。

```python
result = client.gallery.get_cover_files(
    album_ids=["default-album-1", "default-album-2"]
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `album_ids` | `List[str]` | 是 | — | 相册ID列表 |
| `thumb_height` | `int` | 否 | `40` | 缩略图高度 |
| `thumb_width` | `int` | 否 | `40` | 缩略图宽度 |
| `thumb_type` | `str` | 否 | `"imgcropa"` | 缩略图类型，默认裁切 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `fileList` | `Dict` | 封面文件，格式为 `{userId: {albumId: fileData}}` |

---

### 3.4 获取 LCD 缩略图 URL `get_thumb_lcd_url()`

获取文件的 LCD 缩略图 URL（含分辨率和旋转信息）。

```python
result = client.gallery.get_thumb_lcd_url(
    files=[{"uniqueId": "xxx", "albumId": "default-album-1"}]
)

if result.get("ok"):
    for item in result["data"]["successList"]:
        url = item["fileUrl"]
        expand = item.get("expand", {})
        resolution = expand.get("resolution", "")
        rotate = expand.get("rotate", "")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `files` | `List[Dict[str, str]]` | — | 文件列表，每项含 `uniqueId` 和 `albumId` |
| `file_type` | `str` | `"1"` | 文件类型，`"1"` = 图片、`"9"` = 视频 |
| `thumb_type` | `str` | `"imgszthm"` | 缩略图类型 |
| `thumb_height` | `int` | `120` | 缩略图高度 |
| `thumb_width` | `int` | `120` | 缩略图宽度 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 缩略图列表，每项含 `fileUrl`、`fileName`、`size`、`sha256`、`expand`(含 `resolution`/`rotate`) |

---

### 3.5 获取文件详细信息 `get_file_detail()`

获取文件详细信息（文件名、URL、大小、sha256 等）。

```python
result = client.gallery.get_file_detail(
    files=[{"albumId": "default-album-1", "uniqueId": "xxx"}]
)

if result.get("ok"):
    for item in result["data"]["fileList"]:
        print(f"文件名: {item['fileName']}, 类型: {item['fileType']}, 大小: {item['size']}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `files` | `List[Dict[str, str]]` | 是 | — | 文件列表，每项含 `albumId` 和 `uniqueId` |
| `owner_id` | `Optional[str]` | 否 | `None` | 所有者ID，`None` 表示自己 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `fileList` | `List` | 文件详情列表，每项含 `fileName`、`fileType`、`fileUrl`、`size`、`sha256`、`favorite`、`createTime` |

---

## 四、文件操作

### 4.1 删除文件（移入回收站） `delete_files()`

删除文件，默认移入回收站。

```python
result = client.gallery.delete_files(
    album_id="default-album-1",
    unique_ids=["xxx", "yyy"],
)

if result.get("ok"):
    success = result["data"]["successList"]
    fail = result["data"]["failList"]
    print(f"成功: {len(success)}, 失败: {len(fail)}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `album_id` | `str` | 是 | — | 相册ID |
| `unique_ids` | `List[str]` | 是 | — | 文件 `uniqueId` 列表 |
| `recycle` | `str` | 否 | `"1"` | `"1"` = 移入回收站 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 成功删除的文件列表 |
| `failList` | `List` | 删除失败的文件列表 |

---

### 4.2 移动文件到其他相册 `move_files()`

将文件从一个相册移动到另一个相册。

```python
result = client.gallery.move_files(
    album_id="default-album-1",
    unique_ids=["xxx"],
    dest_album_id="自定义相册ID",
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `album_id` | `str` | 是 | — | 源相册ID |
| `unique_ids` | `List[str]` | 是 | — | 文件 `uniqueId` 列表 |
| `dest_album_id` | `str` | 是 | — | 目标相册ID |
| `source_path` | `str` | 否 | `""` | 源路径 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 成功移动的文件列表 |
| `failList` | `List` | 移动失败的文件列表 |

---

### 4.3 收藏/取消收藏 `update_favorite()`

收藏或取消收藏文件。

```python
# 收藏
result = client.gallery.update_favorite(
    unique_id="xxx", album_id="default-album-1", favorite=True
)

# 取消收藏
result = client.gallery.update_favorite(
    unique_id="xxx", album_id="default-album-1", favorite=False
)
```

> **注意**：此接口为电脑端（Web）的收藏接口，与手机端的收藏机制不同。通过此接口收藏的图片仅在电脑端可见，不会同步到手机端收藏列表。

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `unique_id` | `str` | 是 | — | 文件 `uniqueId` |
| `album_id` | `str` | 是 | — | 相册ID |
| `favorite` | `bool` | 否 | `True` | `True` = 收藏，`False` = 取消收藏 |

---

## 五、回收站

回收站操作与手机端隔离——手机端无法看到电脑端回收站里的文件，电脑端回收站列表也无法看到手机删除的照片。

### 5.1 从回收站恢复文件 `restore_files()`

将回收站中的文件恢复到原相册。

```python
result = client.gallery.restore_files(unique_ids=["xxx", "yyy"])

if result.get("ok"):
    print(f"恢复: {len(result['data']['successList'])}个, 失败: {len(result['data']['failList'])}个")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `unique_ids` | `List[str]` | 是 | 文件 `uniqueId` 列表 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 恢复成功的文件列表 |
| `failList` | `List` | 恢复失败的文件列表 |

---

### 5.2 永久删除回收站文件 `delete_recycle_files()`

永久删除回收站中的文件，**不可恢复**。

```python
result = client.gallery.delete_recycle_files(
    album_id="default-album-1",
    unique_ids=["xxx"],
)
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `album_id` | `str` | 是 | 相册ID |
| `unique_ids` | `List[str]` | 是 | 文件 `uniqueId` 列表 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 删除成功的文件列表 |
| `failList` | `List` | 删除失败的文件列表 |

---

### 删除流程总结

```
正常文件
    │
    ▼  delete_files()
回收站文件
    │
    ├──▶ restore_files()          ──▶  恢复为正常文件
    │
    └──▶ delete_recycle_files()   ──▶  永久删除（不可恢复）
```

---

## 六、分享查询

### 6.1 查询分享列表 `query_share()`

查询图库分享列表，同时调用 `queryShare` 和 `queryGroupShare`（当 `v2Flag=True` 时），合并返回完整的分享信息。

```python
result = client.gallery.query_share()

if result.get("ok"):
    data = result["data"]
    print(f"自己的分享: {len(data['ownShareList'])}条")
    print(f"自己的群组分享: {len(data['ownGroupShareList'])}条")
    print(f"收到的分享: {len(data['recShareList'])}条")
    print(f"收到的群组分享: {len(data['recGroupShareList'])}条")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `resource` | `str` | `"album"` | 资源类型 |
| `flag` | `int` | `3` | 标志位 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `ownShareList` | `List` | 自己的分享列表 |
| `ownGroupShareList` | `List` | 自己的群组分享列表 |
| `recShareList` | `List` | 收到的分享列表 |
| `recGroupShareList` | `List` | 收到的群组分享列表 |
| `v2Flag` | `bool` | 是否支持群组分享 |

---

## 七、上传文件

### 7.1 上传图片/视频 `upload_file()`

上传图片或视频到图库（完整流程）。

基于 `uploadType=content` 协议的上传流程：

1. `preUploadAlbumProcess`（获取 lock）
2. `preUploadAlbumProcess`（生成签名）
3. `POST multipart/form-data` 一次上传文件（带 `x-hw-signature` + `x-hw-properties`）
4. `createAlbumFile`
5. `afterUploadAlbumProcess`

```python
# 上传图片到相机相册（默认）
result = client.gallery.upload_file("photo.jpg")

# 上传视频到自定义相册
result = client.gallery.upload_file(
    file_path="video.mp4",
    album_id="自定义相册ID",
    file_type="9",
)

if result.get("ok"):
    print(f"上传成功: {result['data']['fileName']}")
    print(f"uniqueId: {result['data']['uniqueId']}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file_path` | `str` | 是 | — | 本地文件路径 |
| `album_id` | `str` | 否 | `"default-album-1"` | 目标相册ID，默认相机相册 |
| `file_type` | `str` | 否 | `"1"` | 文件类型，`"1"` = 图片、`"9"` = 视频 |
| `source_path` | `str` | 否 | `""` | 来源路径（模拟手机路径） |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `fileName` | `str` | 文件名 |
| `uniqueId` | `str` | 文件唯一ID |
| `thumbUrl` | `str` | 缩略图URL |
| `sdsctime` | `str` | 时间戳 |

---

## 八、下载文件

### 8.1 下载图库文件（底层方法） `download_file()`

直接通过 URL 下载文件。

```python
# 先获取 URL，再下载
urls_result = client.gallery.get_file_urls(
    files=[{"uniqueId": "xxx", "albumId": "default-album-1"}],
)
if urls_result.get("ok"):
    file_url = urls_result["data"]["urlList"][0]["url"]
    result = client.gallery.download_file(file_url, save_path="./download/photo.jpg")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_url` | `str` | 是 | 文件 URL（从 `get_file_urls` / `get_file_detail` 获取） |
| `save_path` | `str` | 是 | 保存路径（含文件名） |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 保存路径 |
| `size` | `int` | 文件大小（字节） |

---

### 8.2 下载图库原图（便捷方法） `download_photo()`

自动获取文件名和下载 URL，下载图库原图。

流程：`queryCloudFileName` → 获取 `fileUrl`/`fileName` → `GET` 下载

```python
result = client.gallery.download_photo(
    unique_id="xxx",
    album_id="default-album-1",
    save_dir="./download",
)

if result.get("ok"):
    print(f"下载完成: {result['data']['path']}, 大小: {result['data']['size']} 字节")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `unique_id` | `str` | 是 | — | 文件 `uniqueId` |
| `album_id` | `str` | 是 | — | 相册ID |
| `save_dir` | `str` | 否 | `"."` | 保存目录 |
| `owner_id` | `Optional[str]` | 否 | `None` | 所有者ID，`None` 表示自己 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 保存路径 |
| `size` | `int` | 文件大小（字节） |

---

### 8.3 批量下载图库原图 `download_photos_batch()`

批量下载图库原图。

```python
result = client.gallery.download_photos_batch(
    files=[
        {"uniqueId": "xxx", "albumId": "default-album-1"},
        {"uniqueId": "yyy", "albumId": "default-album-1"},
    ],
    save_dir="./download",
)

if result.get("ok"):
    print(f"成功: {len(result['data']['successList'])}, 失败: {len(result['data']['failList'])}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `files` | `List[Dict[str, str]]` | 是 | — | 文件列表，每项含 `uniqueId` 和 `albumId` |
| `save_dir` | `str` | 否 | `"."` | 保存目录 |
| `owner_id` | `Optional[str]` | 否 | `None` | 所有者ID，`None` 表示自己 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 成功列表，每项含 `uniqueId`、`path`、`size` |
| `failList` | `List` | 失败列表，每项含 `uniqueId`、`reason` |

---

## 九、完整示例

### 9.1 查询 → 浏览 → 下载

```python
# 1. 获取图库统计
stat = client.gallery.get_stat_info()
print(f"照片: {stat['data']['photoNum']}, 视频: {stat['data']['videoNum']}")

# 2. 查询相册列表
albums = client.gallery.query_albums()
for album in albums["data"]["albumList"]:
    print(f"  {album['albumName']}: {album.get('photoNum', 0)}张照片")

# 3. 获取相机相册中的文件
files = client.gallery.get_files(album_id="default-album-1", count=5)
if files["data"]["fileList"]:
    first = files["data"]["fileList"][0]
    # 4. 下载第一张照片
    result = client.gallery.download_photo(
        unique_id=first["uniqueId"],
        album_id="default-album-1",
        save_dir="./download",
    )
    print(f"下载: {result.get('msg')}")
```

### 9.2 上传 → 移动 → 收藏

```python
# 1. 创建自定义相册
album = client.gallery.create_album("旅行照片")
album_id = album["data"]["albumId"]

# 2. 上传图片到新相册
upload = client.gallery.upload_file(
    file_path="travel.jpg",
    album_id=album_id,
)
print(f"上传: {upload.get('msg')}")

# 3. 收藏该图片
unique_id = upload["data"]["uniqueId"]
fav = client.gallery.update_favorite(
    unique_id=unique_id,
    album_id=album_id,
    favorite=True,
)
print(f"收藏: {fav.get('msg')}")
```

### 9.3 删除 → 恢复 → 永久删除

```python
# 1. 删除文件（移入回收站）
result = client.gallery.delete_files(
    album_id="default-album-1",
    unique_ids=["xxx"],
)

# 2. 查看回收站
recycle = client.gallery.get_files(file_type="4")

# 3. 恢复文件
result = client.gallery.restore_files(unique_ids=["xxx"])

# 4. 或者永久删除
result = client.gallery.delete_recycle_files(
    album_id="default-album-1",
    unique_ids=["xxx"],
)
```

---

## 十、API 速查表

| 方法 | 对应接口 | 说明 |
|------|----------|------|
| `get_stat_info()` | `POST /album/galleryStatInfo` | 获取图库统计信息 |
| `get_date_stat_info()` | `POST /album/galleryDateStatInfo` | 按日期统计 |
| `get_album_stat_info()` | `POST /album/galleryAlbumStatInfo` | 获取相册统计 |
| `get_album_status()` | `POST /album/queryAlbumStatus` | 获取云同步状态 |
| `get_server_time()` | `POST /album/getTime` | 获取服务器时间 |
| `query_albums()` | `POST /album/queryAlbumInfo` | 查询相册列表 |
| `create_album()` | `POST /album/createAlbum` | 创建自定义相册 |
| `get_files()` | `POST /album/getSimpleFile` | 获取文件列表 |
| `get_file_urls()` | `POST /album/getSingleUrl` | 获取文件缩略图/下载 URL |
| `get_cover_files()` | `POST /album/getCoverFiles` | 获取相册封面文件 |
| `get_thumb_lcd_url()` | `POST /album/getThumbLcdUrl` | 获取 LCD 缩略图 URL |
| `get_file_detail()` | `POST /album/queryCloudFileName` | 获取文件详细信息 |
| `delete_files()` | `POST /album/deleteAlbumFile` | 删除文件（移入回收站） |
| `move_files()` | `POST /album/moveAlbumFile` | 移动文件到其他相册 |
| `update_favorite()` | `POST /album/updateFavorite` | 收藏/取消收藏 |
| `restore_files()` | `POST /album/restoreRecycleFiles` | 从回收站恢复文件 |
| `delete_recycle_files()` | `POST /album/deleteRecycleFiles` | 永久删除回收站文件 |
| `query_share()` | `POST /album/queryShare` + `/album/queryGroupShare` | 查询分享列表 |
| `upload_file()` | 多步流程（见上传章节） | 上传图片/视频 |
| `download_file()` | `GET {file_url}` | 下载文件（底层方法） |
| `download_photo()` | `queryCloudFileName` + `GET` | 下载原图（便捷方法） |
| `download_photos_batch()` | 循环调用 `download_photo` | 批量下载原图 |
