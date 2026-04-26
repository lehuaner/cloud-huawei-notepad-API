# 华为云空间 · 备忘录模块使用文档

## 概述

备忘录模块 (`NotepadModule`) 封装了华为云空间 Web 端备忘录 API，支持笔记和标签的查询、创建、更新、同步，以及涂鸦数据获取、附件上传下载等功能。

通过 `client.notepad` 访问：

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
    "msg": "3条笔记",     # 结果描述
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

## 一、标签管理

### 1.1 获取标签列表 `get_tags()`

获取所有标签（笔记分组），包括待办标签和普通标签。

```python
result = client.notepad.get_tags()

if result.get("ok"):
    data = result["data"]
    print(f"待办标签: {len(data['backLoglist'])}个")
    print(f"普通标签: {len(data['noteList'])}个")
    for tag in data["noteList"]:
        print(f"  标签: {tag.get('name')} (GUID: {tag['guid']})")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `simplify` | `bool` | `True` | 是否精简返回数据，精简时仅保留 etag、guid、name、type、color 等关键字段 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `backLoglist` | `List` | 待办标签列表 |
| `noteList` | `List` | 普通标签列表 |

---

### 1.2 根据 tagGuids 获取标签 `get_tags_with_guids()`

根据标签 GUID 获取指定标签信息。

```python
result = client.notepad.get_tags_with_guids("tag-guid-1,tag-guid-2")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tag_guids` | `str` | 是 | 标签 GUID，多个用逗号分隔 |

---

## 二、笔记管理

### 2.1 获取笔记列表 `get_notes_list()`

获取所有笔记和待办任务列表。

```python
result = client.notepad.get_notes_list()

if result.get("ok"):
    data = result["data"]
    print(f"笔记: {len(data['noteList'])}条")
    print(f"待办: {len(data['taskList'])}条")
    print(f"已删除: {len(data['discardList'])}条")
    for note in data["noteList"]:
        print(f"  标题: {note.get('title')} (GUID: {note['guid']})")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `index` | `int` | `0` | 分页索引 |
| `status` | `int` | `0` | 状态 |
| `guids` | `str` | `""` | 笔记 GUIDs |
| `simplify` | `bool` | `True` | 是否精简返回数据 |

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `noteList` | `List` | 笔记列表 |
| `taskList` | `List` | 待办任务列表 |
| `discardList` | `List` | 已删除列表 |

---

### 2.2 获取笔记详情 `get_note_detail()`

获取指定笔记的详细内容。

```python
result = client.notepad.get_note_detail(guid="note-guid-here")

if result.get("ok"):
    data = result["data"]
    print(f"标题: {data.get('title')}")
    print(f"内容: {data.get('content')}")
    print(f"创建时间: {data.get('created')}")
    print(f"修改时间: {data.get('modified')}")
    print(f"HTML内容: {data.get('html_content')}")
    print(f"附件数: {data.get('attachment_count')}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `guid` | `str` | 是 | — | 笔记 GUID（从 `get_notes_list` 返回的 `guid` 字段获取） |
| `kind` | `str` | 否 | `"newnote"` | 笔记类型，现代备忘录为 `"newnote"`，老格式为 `"note"` |
| `start_cursor` | `str` | 否 | `None` | 同步游标 |

---

### 2.3 创建笔记 `create_note()`

创建新笔记。

```python
result = client.notepad.create_note(
    title="测试标题",
    content_text="测试内容",
)

if result.get("ok"):
    print(f"创建成功, GUID: {result['data']['guid']}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `title` | `str` | 是 | — | 笔记标题 |
| `content_text` | `str` | 是 | — | 笔记内容（纯文本） |
| `tag_id` | `str` | 否 | `""` | 标签ID |

---

### 2.4 更新笔记 `update_note()`

更新已有笔记的内容。需要提供 `guid` 和 `etag`。

```python
result = client.notepad.update_note(
    guid="note-guid",
    etag="1",
    title="新标题",
    content_text="新内容",
)

if result.get("ok"):
    print("更新成功")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `guid` | `str` | 是 | — | 笔记 GUID |
| `etag` | `str \| int` | 是 | — | 笔记版本标签（从 `get_notes_list` 或 `get_note_detail` 获取） |
| `title` | `str` | 是 | — | 新标题 |
| `content_text` | `str` | 是 | — | 新内容 |
| `tag_id` | `str` | 否 | `""` | 标签ID |
| `created_time` | `int` | 否 | `None` | 原始创建时间（毫秒时间戳） |
| `start_cursor` | `str` | 否 | `None` | 同步游标 |

---

### 2.5 同步操作 `sync()`

同步备忘录数据到云端。创建或更新笔记后建议调用。

```python
result = client.notepad.sync()

if result.get("ok"):
    print(f"同步成功, needSync: {result['data']['needSync']}")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `ctag_note_info` | `str` | `""` | 笔记 ctag 信息 |
| `ctag_task_info` | `str` | `""` | 任务 ctag 信息 |
| `start_cursor` | `str` | `None` | 同步游标 |

---

## 三、待办任务

### 3.1 查询待办任务详情 `get_task_detail()`

查询指定待办任务的详细内容。

```python
result = client.notepad.get_task_detail(guid="task-guid")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `guid` | `str` | 是 | — | 任务 GUID |
| `ctag_task_info` | `str` | 否 | `""` | 任务 ctag 信息 |
| `start_cursor` | `str` | 否 | `None` | 同步游标 |

---

## 四、涂鸦与附件

### 4.1 获取涂鸦数据 `get_graffiti_data()`

获取手写/涂鸦笔记的图片数据。

```python
result = client.notepad.get_graffiti_data(
    asset_id="xxx",
    record_id="yyy",
    version_id="zzz",
    kind="newnote",
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `asset_id` | `str` | 是 | — | 资源ID |
| `record_id` | `str` | 是 | — | 记录ID |
| `version_id` | `str` | 是 | — | 版本ID |
| `kind` | `str` | 否 | `"newnote"` | 笔记类型 |

---

### 4.2 附件上传预处理 `pre_upload_attachment_process()`

为附件上传获取签名和锁定。

```python
result = client.notepad.pre_upload_attachment_process(
    need_to_sign_url="/proxy/v1/upload/%2Fv2%2F1001%2Fnote%2Frecord%2F...",
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `need_to_sign_url` | `str` | 是 | — | 需要签名的上传路径 |
| `http_method` | `str` | 否 | `"POST"` | HTTP 方法 |
| `generate_sign_flag` | `bool` | 否 | `True` | 是否生成签名 |
| `first_upload_file_flag` | `bool` | 否 | `True` | 是否首次上传 |

---

### 4.3 附件上传后处理 `after_upload_attachment_process()`

在附件上传完成后调用，确认上传。

```python
result = client.notepad.after_upload_attachment_process()
```

---

### 4.4 下载附件 `download_attachment()`

通过预签名 URL 下载附件。

```python
# 保存到文件
result = client.notepad.download_attachment(
    file_path="/proxy/v1/download/...",
    save_path="attachment.jpg",
)

# 获取二进制内容
result = client.notepad.download_attachment(
    file_path="/proxy/v1/download/...",
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file_path` | `str` | 是 | — | 文件路径 |
| `save_path` | `str` | 否 | `None` | 保存路径，为 None 则返回二进制内容 |

---

### 4.5 获取附件下载URL `get_attachment_download_url()`

获取附件的预签名下载 URL。

```python
result = client.notepad.get_attachment_download_url(
    file_path="/proxy/v1/download/...",
)
```

---

## 五、ETags 更新

### 5.1 更新标签 ETags `update_note_tags_etags()`

更新标签的 ETags 信息。

```python
result = client.notepad.update_note_tags_etags(note_tags=[...])
```

### 5.2 更新笔记 ETags `update_notes_etags()`

更新笔记的 ETags 信息。

```python
result = client.notepad.update_notes_etags(
    note_list=[...],
    discard_list=[],
)
```

---

## 六、文件预签名

### 6.1 文件预签名 `pre_process_file()`

获取文件操作的预签名。

```python
result = client.notepad.pre_process_file(
    need_to_sign_url="/some/path",
    http_method="GET",
    generate_sign_flag=True,
)
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `need_to_sign_url` | `str` | `""` | 需要签名的 URL 路径 |
| `http_method` | `str` | `"GET"` | HTTP 方法 |
| `generate_sign_flag` | `bool` | `False` | 是否生成签名 |

---

## 七、API 速查表

| 方法 | 对应接口 | 说明 |
|------|----------|------|
| `get_tags()` | `POST /notepad/notetag/query` | 获取标签列表 |
| `get_tags_with_guids()` | `POST /notepad/notetag/query` | 根据 GUID 获取标签 |
| `get_notes_list()` | `POST /notepad/simplenote/query` | 获取笔记列表 |
| `get_note_detail()` | `POST /notepad/note/query` | 获取笔记详情 |
| `create_note()` | `POST /notepad/note/create` | 创建笔记 |
| `update_note()` | `POST /notepad/note/update` | 更新笔记 |
| `sync()` | `POST /notepad/sync` | 同步操作 |
| `get_task_detail()` | `POST /notepad/task/query` | 查询待办任务详情 |
| `get_graffiti_data()` | `GET /proxyserver/getGraffitiData4V2` | 获取涂鸦数据 |
| `pre_upload_attachment_process()` | `POST /driveFileProxy/preUploadAttachmentProcess` | 附件上传预处理 |
| `after_upload_attachment_process()` | `POST /driveFileProxy/afterUploadAttachmentProcess` | 附件上传后处理 |
| `download_attachment()` | `GET {file_path}` | 下载附件 |
| `get_attachment_download_url()` | `POST /proxyserver/driveFileProxy/preProcess` | 获取附件下载URL |
| `update_note_tags_etags()` | `POST /notepad/notetag/etags` | 更新标签 ETags |
| `update_notes_etags()` | `POST /notepad/note/etags` | 更新笔记 ETags |
| `pre_process_file()` | `POST /proxyserver/driveFileProxy/preProcess` | 文件预签名 |
