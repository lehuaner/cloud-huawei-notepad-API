# cloud-space-huawei

华为云空间 (Huawei Cloud Space) Python SDK，提供登录、备忘录、联系人、图库、云盘、查找设备等接口。

[English](./README_EN.md)

## 安装

```bash
git clone https://github.com/your-repo/cloud-space-huawei.git
cd cloud-space-huawei
pip install -e .
```

依赖：Python >= 3.8，`requests >= 2.28`

## 快速开始

### 1. 账号密码登录

```python
from cloud_space_huawei import HuaweiCloudClient

client = HuaweiCloudClient()

# 首次登录
result = client.login("手机号", "密码")

if result.need_verify:
    # 新设备需要验证码
    code = input("请输入验证码: ")
    result = client.verify_device(code)

if result:
    # 保存 cookies，下次直接用 cookies 登录即可跳过设备验证
    cookies = result.cookies
    print(f"登录成功! userId={cookies.get('userId')}")
```

### 2. 从 cookies 恢复会话

```python
from cloud_space_huawei import HuaweiCloudClient

# 从之前保存的 cookies 创建
client = HuaweiCloudClient.from_cookies(cookies)
```

### 3. 使用已有 cookies 跳过设备验证

```python
from cloud_space_huawei import HuaweiCloudClient

client = HuaweiCloudClient()

# 传入之前已认证过的cookies，可跳过新设备验证
result = client.login("手机号", "密码", cookies=cookies)
```

### 4. 使用备忘录

```python
# 获取笔记列表
result = client.notepad.get_notes_list()
if result["ok"]:
    for note in result["data"]["noteList"]:
        print(f"笔记: {note.get('title', '')} (GUID: {note['guid']})")

# 获取笔记详情
result = client.notepad.get_note_detail(guid="note-guid-here")

# 创建新笔记
result = client.notepad.create_note(title="测试标题", content_text="测试内容")
if result["ok"]:
    client.notepad.sync()  # 同步到云端

# 更新笔记 (需要 guid 和 etag)
result = client.notepad.update_note(
    guid="note-guid", etag="1", title="新标题", content_text="新内容"
)
if result["ok"]:
    client.notepad.sync()
```

### 5. 使用其他模块

```python
# 联系人 (尚未实现)
# client.contacts.get_contacts()

# 图库 (尚未实现)
# client.gallery.get_albums()

# 云盘 (尚未实现)
# client.drive.list_files()

# 查找设备 (尚未实现)
# client.find_device.get_device_list()
```

### 6. 自由发挥 — 直接操作 session

```python
# 底层 requests.Session 完全开放
resp = client.session.get("https://cloud.huawei.com/some-api")
print(resp.json())

# 手动管理 cookies
cookies = {c.name: c.value for c in client.session.cookies}
```

## API 参考

### 核心客户端 `HuaweiCloudClient`

| 方法 | 说明 |
|------|------|
| `login(phone, password, cookies=None)` | 账号密码登录，返回 `LoginResult` |
| `verify_device(verify_code)` | 提交设备验证码 |
| `from_cookies(cookies)` | 类方法，从 cookies dict 恢复会话 |
| `get_common_param(simplify=True)` | 获取通用参数，simplify=True 时精简返回 |
| `get_home_data(simplify=True)` | 获取首页数据 (含 deviceIdForHeader)，simplify=True 时精简返回 |
| `get_cookies()` | 查询服务端 Cookie 值 |
| `heartbeat_check()` | 心跳检测，保持会话活跃 |
| `notify_poll(tag, module, timeout)` | 通知轮询 (长轮询) |
| `get_space_info(simplify=True)` | 获取云空间容量信息，simplify=True 时精简返回 |
| `refresh_cookies()` | 刷新 cookies 并更新客户端状态 |

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `cookies` | `dict` | 当前 cookies 字典 |
| `notepad` | `NotepadModule` | 备忘录模块 |
| `contacts` | `ContactsModule` | 联系人模块 (骨架) |
| `gallery` | `GalleryModule` | 图库模块 (骨架) |
| `drive` | `DriveModule` | 云盘模块 (骨架) |
| `find_device` | `FindDeviceModule` | 查找设备模块 (骨架) |

### `LoginResult`

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 是否成功 |
| `need_verify` | `bool` | 是否需要二次验证 |
| `cookies` | `dict` | 登录后的 cookies（含信任设备信息，保存后下次可跳过验证） |
| `auth_devices` | `list` | 验证设备列表 |
| `error` | `str` | 错误信息 |

### 备忘录 `NotepadModule`

| 方法 | 说明 |
|------|------|
| `get_tags(simplify=True)` | 获取标签列表，simplify=True 时精简返回 |
| `get_notes_list(index, status, guids, simplify=True)` | 获取笔记列表，simplify=True 时精简返回 |
| `get_note_detail(guid, kind, start_cursor)` | 获取笔记详情 |
| `create_note(title, content_text, tag_id)` | 创建新笔记 |
| `update_note(guid, etag, title, content_text, ...)` | 更新笔记 |
| `sync(ctag_note_info, ctag_task_info, start_cursor)` | 同步操作 |
| `get_task_detail(guid, ctag_task_info, start_cursor)` | 查询待办任务详情 |
| `get_graffiti_data(asset_id, record_id, version_id, kind)` | 获取涂鸦数据 |
| `pre_process_file(need_to_sign_url, http_method, generate_sign_flag)` | 文件预签名 |
| `get_common_param(simplify=True)` | 获取通用参数，simplify=True 时精简返回 |
| `get_home_data(simplify=True)` | 获取首页数据，simplify=True 时精简返回 |
| `get_cookies()` | 查询 Cookie 值 |
| `heartbeat_check()` | 心跳检测 |
| `notify_poll(tag, module, timeout)` | 通知轮询 |
| `get_space_info(simplify=True)` | 获取云空间容量信息，simplify=True 时精简返回 |
| `refresh_cookies()` | 刷新 cookies |

### 统一返回格式

所有子模块方法返回统一格式：

```python
{
    "ok": bool,       # 操作是否成功
    "code": str,      # 状态码，"0" 表示成功
    "msg": str,       # 人类可读的消息
    "data": ...       # 具体数据
}
```

## 设计理念

1. **简单易用**: `HuaweiCloudClient` 是唯一入口，登录后即可使用所有模块
2. **用户掌控**: `cookies` 完全交给用户保存，SDK 不做任何存储假设
3. **自由发挥**: 底层 `requests.Session` 完全暴露，用户可以自由定制请求
4. **模块化**: 各功能模块独立，按需加载，未实现的模块不会影响已实现的功能

## 日志

SDK 使用 Python 标准库 `logging`，logger 名称为 `cloud-space-huawei`：

```python
import logging
logging.getLogger("cloud-space-huawei").setLevel(logging.DEBUG)
```

## License

[MIT](./LICENSE)
