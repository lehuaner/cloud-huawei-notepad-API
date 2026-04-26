# 华为云空间 · 云盘模块使用文档

## 概述

云盘模块 (`DriveModule`) 封装了华为云空间 Web 端云盘 API，支持云盘文件的查询、创建、删除、恢复、移动、重命名、上传、下载等功能。

通过 `client.drive` 访问：

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

## 一、文件查询

### 1.1 列出文件 `list_files()`

列出云盘中的文件和文件夹。

```python
# 列出根目录文件
result = client.drive.list_files()

# 列出指定文件夹
result = client.drive.list_files(folder_id="Btxah8V8B5niKyxrFUNNJ_74DQLNbAeV4")

# 分页查询
result = client.drive.list_files(cursor="397568")

# 按修改时间降序排列
result = client.drive.list_files(order="editedTime desc")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `folder_id` | `str` | `""` | 文件夹ID，默认为根目录 `"root"` |
| `order` | `str` | `"editedTime desc"` | 排序方式 |
| `cursor` | `str` | `""` | 分页游标，用于翻页 |
| `folder_flag` | `int` | `3` | 显示模式，`3`=所有，`1`=只显示文件夹，`2`=只显示文件 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `files` | `List` | 文件列表 |
| `nextCursor` | `str` | 下一页游标 |
| `serverTime` | `int` | 服务器时间（毫秒） |

**文件对象字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 文件ID |
| `fileName` | `str` | 文件名 |
| `mimeType` | `str` | MIME类型，文件夹为 `application/vnd.huawei-apps.folder` |
| `size` | `int` | 文件大小（字节） |
| `sha256` | `str` | SHA256哈希 |
| `createdTime` | `int` | 创建时间（毫秒） |
| `editedTime` | `int` | 修改时间（毫秒） |
| `recycled` | `bool` | 是否在回收站 |
| `parentFolder` | `List` | 父文件夹ID列表 |
| `contentDownloadLink` | `str` | 下载链接 |
| `thumbnailDownloadLink` | `str` | 缩略图链接 |
| `smallThumbnailDownloadLink` | `str` | 小缩略图链接 |
| `pictureMetadata` | `dict` | 图片元信息（宽高等） |
| `version` | `int` | 文件版本号 |

---

### 1.2 获取文件详情 `get_file_detail()`

获取指定文件的详细信息。

```python
result = client.drive.get_file_detail("BoAZIpf2QpTPdu4unm5dDwKkTqef5kKYz")

if result.get("ok"):
    file_info = result["data"]
    print(f"文件名: {file_info['fileName']}")
    print(f"大小: {file_info['size']} 字节")
    print(f"SHA256: {file_info['sha256']}")
    print(f"下载链接: {file_info['contentDownloadLink']}")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_id` | `str` | 是 | 文件ID |

**返回 `data` 字段：**

完整的文件对象，字段同上。

---

### 1.3 获取缩略图URL `get_thumbnail_url()`

获取文件的缩略图URL。

```python
result = client.drive.get_thumbnail_url("BoAZIpf2QpTPdu4unm5dDwKkTqef5kKYz")

if result.get("ok"):
    print(f"缩略图: {result['data']['thumbnailUrl']}")
    print(f"小缩略图: {result['data']['smallThumbnailUrl']}")
```

---

## 二、文件夹操作

### 2.1 创建文件夹 `create_folder()`

在云盘中创建新文件夹。

```python
# 在根目录创建
result = client.drive.create_folder("新建文件夹")

# 在指定目录创建
result = client.drive.create_folder(
    name="子文件夹",
    parent_id="Btxah8V8B5niKyxrFUNNJ_74DQLNbAeV4"
)

if result.get("ok"):
    folder_id = result["data"]["id"]
    print(f"创建成功，文件夹ID: {folder_id}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `str` | 是 | — | 文件夹名称 |
| `parent_id` | `str` | 否 | `"root"` | 父文件夹ID，默认为根目录 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 新创建的文件夹ID |
| `fileName` | `str` | 文件夹名称 |
| `mimeType` | `str` | MIME类型 |
| `createdTime` | `int` | 创建时间 |
| `editedTime` | `int` | 修改时间 |
| `parentFolder` | `List` | 父文件夹ID |
| `recycled` | `bool` | 是否在回收站 |

---

## 三、文件删除与恢复

### 3.1 删除文件 `delete_files()`

删除文件，默认移入回收站。

```python
# 删除单个文件
result = client.drive.delete_files([
    {"fieldId": "BvCX2wnEMOgdtisWqDPdBtrUwF4B1DDkH", "baseVersion": 1}
])

# 删除多个文件
result = client.drive.delete_files([
    {"fieldId": "file_id_1", "baseVersion": 1},
    {"fieldId": "file_id_2", "baseVersion": 2},
])

if result.get("ok"):
    print(f"成功: {result['data']['successList']}")
    print(f"失败: {result['data']['failList']}")
```

> **注意**：`baseVersion` 可以从 `get_file_detail()` 或 `list_files()` 返回的 `version` 字段获取。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_ids` | `List[Dict]` | 是 | 文件ID列表，每项包含 `fieldId` 和 `baseVersion` |
| `src_path` | `str` | 否 | 源路径（URL编码） |
| `del_type` | `int` | 否 | 删除类型，`0`=移入回收站 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 成功删除的文件ID列表 |
| `failList` | `List` | 删除失败的文件列表 |

---

### 3.2 批量删除 `batch_delete()`

批量删除文件，简化版接口。

```python
result = client.drive.batch_delete(["file_id_1", "file_id_2", "file_id_3"])
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_ids` | `List[str]` | 是 | 文件ID列表 |
| `versions` | `List[int]` | 否 | 版本号列表，默认为 `[1]` |

---

### 3.3 恢复文件 `restore_files()`

从回收站恢复文件。

```python
# 恢复单个文件
result = client.drive.restore_files(["BvCX2wnEMOgdtisWqDPdBtrUwF4B1DDkH"])

# 批量恢复
result = client.drive.restore_files(["file_id_1", "file_id_2"])

if result.get("ok"):
    print(f"成功: {result['data']['successList']}")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_ids` | `List[str]` | 是 | 要恢复的文件ID列表 |
| `cursor` | `str` | 否 | 分页游标 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 成功恢复的文件ID列表 |
| `newSuccessList` | `List` | 新成功列表（含编辑时间） |
| `failList` | `List` | 恢复失败的文件列表 |

---

### 3.4 批量恢复 `batch_restore()`

批量恢复文件，简化版接口。

```python
result = client.drive.batch_restore(["file_id_1", "file_id_2", "file_id_3"])
```

---

## 四、文件移动与重命名

### 4.1 移动文件 `move_files()`

将文件移动到指定文件夹。

```python
# 移动单个文件
result = client.drive.move_files(
    file_ids=["Bn5Fxs5DbT77jYJqP9CFO3ZaEkPGU20y-"],
    dest_folder_id="BnW69crabQnagDKvnsS5Ph5R7XDCym0F2"
)

# 批量移动
result = client.drive.move_files(
    file_ids=["file_id_1", "file_id_2"],
    dest_folder_id="destination_folder_id"
)

if result.get("ok"):
    print(f"成功: {result['data']['successList']}")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_ids` | `List[str]` | 是 | 要移动的文件ID列表 |
| `dest_folder_id` | `str` | 是 | 目标文件夹ID |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `successList` | `List` | 成功移动的文件ID列表 |
| `failList` | `List` | 移动失败的文件列表 |

---

### 4.2 批量移动 `batch_move()`

批量移动文件，简化版接口。

```python
result = client.drive.batch_move(
    file_ids=["file_id_1", "file_id_2"],
    dest_folder_id="destination_folder_id"
)
```

---

### 4.3 重命名文件 `rename_file()`

重命名文件或文件夹。

```python
result = client.drive.rename_file(
    file_id="BghWZ2xqc26_saWxTIRJJ3osAeJkenNiv",
    new_name="新文件名.txt"
)

if result.get("ok"):
    print(f"新文件名: {result['data']['fileName']}")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_id` | `str` | 是 | 文件ID |
| `new_name` | `str` | 是 | 新名称（支持URL编码） |

**返回 `data` 字段：**

完整的文件对象，包含更新后的信息。

---

### 4.4 批量重命名 `batch_rename()`

批量重命名文件。

```python
result = client.drive.batch_rename([
    {"fileId": "file_id_1", "newName": "文件1.txt"},
    {"fileId": "file_id_2", "newName": "文件2.txt"},
])

if result.get("ok"):
    print(f"成功: {len(result['data']['successList'])}个")
    print(f"失败: {len(result['data']['failList'])}个")
```

---

## 五、文件上传

### 5.1 上传文件 `upload_file()`

上传文件到云盘（完整流程）。

```python
# 上传到根目录
result = client.drive.upload_file("C:/Users/test/photo.jpg")

# 上传到指定文件夹
result = client.drive.upload_file(
    file_path="C:/Users/test/document.pdf",
    parent_folder_id="Btxah8V8B5niKyxrFUNNJ_74DQLNbAeV4",
)

if result.get("ok"):
    print(f"上传成功!")
    print(f"文件ID: {result['data']['fileId']}")
    print(f"文件名: {result['data']['fileName']}")
    print(f"大小: {result['data']['size']} 字节")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file_path` | `str` | 是 | — | 本地文件路径 |
| `parent_folder_id` | `str` | 否 | `"root"` | 父文件夹ID |
| `chunk_size` | `int` | 否 | `5242880` (5MB) | 分片大小 |
| `show_in_recent` | `bool` | 否 | `True` | 是否显示在最近列表 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 云盘中的文件ID |
| `fileName` | `str` | 文件名 |
| `size` | `int` | 文件大小 |
| `sha256` | `str` | SHA256哈希 |

---

### 5.2 上传预处理 `pre_upload_process()`

获取文件上传签名。

```python
result = client.drive.pre_upload_process()

if result.get("ok"):
    print(f"签名: {result['data']['sign']}")
    print(f"时间戳: {result['data']['requestTimeStamp']}")
```

---

## 六、文件下载

### 6.1 下载文件 `download_file()`

下载云盘文件到本地。

```python
# 下载到当前目录
result = client.drive.download_file(
    file_id="Bo9XkJnqP2fUHsevBpGhJs6rABWR-j9r1",
    save_path="C:/Users/test/download.png"
)

# 下载并获取内容
result = client.drive.download_file(
    file_id="file_id",
    save_path=""  # 不保存，直接返回内容
)

if result.get("ok"):
    print(f"保存路径: {result['data']['path']}")
    print(f"文件大小: {result['data']['size']} 字节")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_id` | `str` | 是 | 文件ID |
| `save_path` | `str` | 否 | 保存路径，为空则返回二进制内容 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 保存路径 |
| `size` | `int` | 文件大小 |
| `fileName` | `str` | 文件名 |

---

### 6.2 下载预处理 `pre_download_process()`

获取文件下载签名，为下载做准备。

```python
result = client.drive.pre_download_process("file_id")

if result.get("ok"):
    print(f"签名: {result['data']['sign']}")
    print(f"时间戳: {result['data']['requestTimeStamp']}")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_id` | `str` | 是 | 文件ID |

**返回 `data` 字段：**

包含签名信息，供 `get_download_url()` 内部使用。

> **注意**：此方法通常由 `get_download_url()` 内部调用，一般无需直接使用。

---

### 6.3 获取下载URL `get_download_url()`

获取文件的下载URL。

```python
result = client.drive.get_download_url("file_id")

if result.get("ok"):
    print(f"下载URL: {result['data']['downloadUrl']}")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_id` | `str` | 是 | 文件ID |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `downloadUrl` | `str` | 下载URL |
| `sign` | `str` | 签名 |
| `requestTimeStamp` | `str` | 时间戳 |
| `fileId` | `str` | 文件ID |

---

### 6.4 下载缩略图 `download_thumbnail()`

下载文件的缩略图。

```python
# 保存到文件
result = client.drive.download_thumbnail(
    file_id="file_id",
    save_path="thumbnail.jpg"
)

# 获取缩略图内容
result = client.drive.download_thumbnail(
    file_id="file_id",
    save_path=""
)
```

---

## 七、完整示例

### 7.1 查询 → 浏览 → 下载

```python
# 1. 列出根目录文件
result = client.drive.list_files()
if not result.get("ok"):
    print("查询失败")
    exit()

files = result["data"]["files"]
print(f"共 {len(files)} 个文件/文件夹")

for f in files:
    if f["mimeType"] == "application/vnd.huawei-apps.folder":
        print(f"📁 {f['fileName']}")
    else:
        print(f"📄 {f['fileName']} ({f['size']} 字节)")

# 2. 获取文件详情
if files:
    first_file = files[0]
    detail = client.drive.get_file_detail(first_file["id"])
    print(f"详情: {detail}")

# 3. 下载文件
if files and files[0]["mimeType"] != "application/vnd.huawei-apps.folder":
    result = client.drive.download_file(
        file_id=files[0]["id"],
        save_path="./download/" + files[0]["fileName"]
    )
    print(f"下载: {result.get('msg')}")
```

### 7.2 创建 → 上传 → 重命名 → 移动

```python
# 1. 创建文件夹
folder = client.drive.create_folder("测试文件夹")
if not folder.get("ok"):
    print("创建失败")
    exit()
folder_id = folder["data"]["id"]

# 2. 上传文件到新文件夹
upload = client.drive.upload_file(
    file_path="test.pdf",
    parent_folder_id=folder_id,
)
if not upload.get("ok"):
    print("上传失败")
    exit()

# 3. 重命名
file_id = upload["data"]["fileId"]
rename = client.drive.rename_file(
    file_id=file_id,
    new_name="正式文档.pdf"
)
print(f"重命名: {rename.get('msg')}")

# 4. 移动到根目录
move = client.drive.move_files(
    file_ids=[file_id],
    dest_folder_id="root"
)
print(f"移动: {move.get('msg')}")
```

### 7.3 批量操作

```python
# 1. 批量删除
result = client.drive.batch_delete([
    "file_id_1",
    "file_id_2",
    "file_id_3",
])
print(f"删除: {result.get('msg')}")

# 2. 批量重命名
result = client.drive.batch_rename([
    {"fileId": "file_id_1", "newName": "新名称1.txt"},
    {"fileId": "file_id_2", "newName": "新名称2.txt"},
])
print(f"重命名: {result.get('msg')}")

# 3. 批量恢复
result = client.drive.batch_restore([
    "file_id_1",
    "file_id_2",
])
print(f"恢复: {result.get('msg')}")
```

---

## 八、API 速查表

| 方法 | 对应接口 | 说明 |
|------|----------|------|
| `list_files()` | `POST /syncDrive/queryDriveFile` | 列出文件 |
| `get_file_detail()` | `POST /syncDrive/queryDriveFile` | 获取文件详情 |
| `get_thumbnail_url()` | `POST /syncDrive/queryDriveFile` | 获取缩略图URL |
| `create_folder()` | `POST /syncDrive/mkDriveFile` | 创建文件夹 |
| `delete_files()` | `POST /syncDrive/delDriveFile` | 删除文件 |
| `batch_delete()` | `POST /syncDrive/delDriveFile` | 批量删除 |
| `restore_files()` | `POST /syncDrive/restoreDriveFile` | 恢复文件 |
| `batch_restore()` | `POST /syncDrive/restoreDriveFile` | 批量恢复 |
| `move_files()` | `POST /syncDrive/moveDriveFile` | 移动文件 |
| `batch_move()` | `POST /syncDrive/moveDriveFile` | 批量移动 |
| `rename_file()` | `POST /syncDrive/renameDriveFile` | 重命名文件 |
| `batch_rename()` | 循环调用 `rename_file` | 批量重命名 |
| `pre_upload_process()` | `POST /proxyserver/driveFileProxy/preProcess` | 上传预处理 |
| `upload_file()` | 多步流程 | 上传文件 |
| `pre_download_process()` | `POST /proxyserver/driveFileProxy/preProcess` | 下载预处理 |
| `get_download_url()` | `GET /drive/v1/files/{id}` | 获取下载URL |
| `download_file()` | `GET {contentDownloadLink}` | 下载文件 |
| `download_thumbnail()` | `GET {thumbnailLink}` | 下载缩略图 |
