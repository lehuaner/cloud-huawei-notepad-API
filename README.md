# Cloud Space API

> ⚠️ **免责声明：本项目仅供学习和研究使用，严禁用于任何商业或非法用途。** 详见 [免责声明](./docs/DISCLAIMER.md)

Cloud Space Python SDK，提供登录、备忘录、联系人、图库、云盘、查找设备、会员/支付、版本管理等接口。

[English](./README_EN.md)

## 安装

```bash
git clone https://github.com/lehuaner/Cloud-Space-API.git
cd Cloud-Space-API
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
    # 新设备需要验证码 — 先获取验证设备列表（同时触发服务端发送验证码）
    send_result = client.send_verify_code(device_index=0)
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
# 联系人
client.contacts.get_contacts()
client.contacts.create_contact({"name": "张三", "phone": "13800138000"})

# 图库
client.gallery.get_stat_info()
client.gallery.query_albums()
client.gallery.get_files(album_id="default-album-1")

# 云盘
client.drive.list_files()
client.drive.upload_file("photo.jpg")
client.drive.download_file(file_id="xxx", save_path="photo.jpg")

# 查找设备
client.find_device.get_device_list()
client.find_device.locate(device_id="xxx", device_type=9)
client.find_device.play_bell(device_id="xxx", device_type=9)

# 会员/支付 ⚠️
client.payment.get_user_grade_info()
client.payment.get_available_grade_packages()

# 版本管理 ⚠️
client.revisions.query_revision_right()
client.revisions.get_revisions(service="addressbook")
```

### 6. 心跳保活

```python
client = HuaweiCloudClient.from_cookies(cookies)

# 启动后台心跳保活线程（自动刷新 CSRFToken）
client.start_heartbeat(interval=300)

# 随时获取最新的 CSRFToken
token = client.csrf_token

# 停止心跳
client.stop_heartbeat()
```

### 7. 自由发挥 — 直接操作 session

```python
# 底层 requests.Session 完全开放
resp = client._session.get("https://cloud.huawei.com/some-api")
print(resp.json())

# 手动管理 cookies
cookies = client.cookies
```

## API 参考

### 核心客户端 `HuaweiCloudClient`

#### 登录 API

| 方法 | 说明 |
|------|------|
| `login(phone, password, cookies=None)` | 账号密码登录，返回 `LoginResult` |
| `send_verify_code(device_index=0)` | 获取验证设备列表（同时触发服务端发送验证码） |
| `verify_device(verify_code)` | 提交设备验证码，完成设备信任认证 |
| `from_cookies(cookies)` | 类方法，从 cookies dict 恢复会话 |
| `logout()` | 登出华为云空间 |

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `cookies` | `dict` | 当前 cookies 字典（从 session 动态同步） |
| `need_verify` | `bool` | 当前会话是否需要设备信任认证 |
| `csrf_token` | `str` | 当前最新的 CSRFToken（心跳线程会自动刷新） |
| `heartbeat_running` | `bool` | 心跳线程是否正在运行 |
| `notepad` | `NotepadModule` | 备忘录模块 |
| `contacts` | `ContactsModule` | 联系人模块 |
| `gallery` | `GalleryModule` | 图库模块 |
| `drive` | `DriveModule` | 云盘模块 |
| `find_device` | `FindDeviceModule` | 查找设备模块 |
| `payment` | `PaymentModule` | 会员/支付模块 ⚠️ |
| `revisions` | `RevisionsModule` | 版本管理模块 ⚠️ |

#### 心跳保活

| 方法 | 说明 |
|------|------|
| `start_heartbeat(interval=300, on_csrf_refresh=None)` | 启动后台心跳保活线程 |
| `stop_heartbeat()` | 停止后台心跳保活线程 |

#### 门户级 API

| 方法 | 说明 |
|------|------|
| `get_common_param(simplify=True)` | 获取通用参数，simplify=True 时精简返回 |
| `get_home_data(simplify=True)` | 获取首页数据 (含 deviceIdForHeader)，simplify=True 时精简返回 |
| `get_cookies()` | 查询服务端 Cookie 值 |
| `heartbeat_check()` | 心跳检测，保持会话活跃 |
| `notify_poll(tag, module, timeout)` | 通知轮询 (长轮询) |
| `get_space_info(simplify=True)` | 获取云空间容量信息，simplify=True 时精简返回 |
| `refresh_cookies()` | 刷新 cookies 并更新客户端状态 |

#### 补充 API

| 方法 | 说明 |
|------|------|
| `get_user_space()` | 获取用户空间详情 |
| `get_family_share_info()` | 获取家庭共享信息 |
| `get_device_and_wallet()` | 获取设备和钱包信息 |
| `get_personal_info()` | 获取个人信息 |
| `get_language_map()` | 获取语言映射 |
| `get_client_log_report()` | 获取客户端日志报告配置 |
| `update_client_log_report(log_data)` | 更新客户端日志报告 |
| `data_extract_query_task()` | 查询数据提取任务 |
| `get_app_info_list_by_consent()` | 获取应用数据管理信息 |
| `get_space_banner_config()` | 获取云空间横幅配置 |

### `LoginResult`

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 是否成功 |
| `need_verify` | `bool` | 是否需要二次验证 |
| `cookies` | `dict` | 登录后的 cookies（含信任设备信息，保存后下次可跳过验证） |
| `auth_devices` | `list` | 验证设备列表 |
| `error` | `str` | 错误信息 |

### 子模块文档

| 模块 | 文档 |
|------|------|
| 联系人 `ContactsModule` | [docs/contacts.md](docs/contacts.md) |
| 图库 `GalleryModule` | [docs/gallery.md](docs/gallery.md) |
| 云盘 `DriveModule` | [docs/drive.md](docs/drive.md) |
| 备忘录 `NotepadModule` | [docs/notepad.md](docs/notepad.md) |
| 查找设备 `FindDeviceModule` | [docs/find_device.md](docs/find_device.md) |
| 会员/支付 `PaymentModule` ⚠️ | [docs/payment.md](docs/payment.md) |
| 版本管理 `RevisionsModule` ⚠️ | [docs/revisions.md](docs/revisions.md) |

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

## ⚠️ 实验性模块

`payment`（会员/支付）和 `revisions`（版本管理）模块**实现尚不完整，且未经严格测试**，可能存在已知或未知的 Bug。使用时请注意：

- 部分接口可能无法正常工作或返回异常数据
- 接口参数和返回格式可能在未来版本中发生变更
- 如发现确切的 Bug，欢迎提交 [Issue](https://github.com/lehuaner/Cloud-Space-API/issues)

## 设计理念

1. **简单易用**: `HuaweiCloudClient` 是唯一入口，登录后即可使用所有模块
2. **用户掌控**: `cookies` 完全交给用户保存，SDK 不做任何存储假设
3. **自由发挥**: 底层 `requests.Session` 完全暴露，用户可以自由定制请求
4. **模块化**: 各功能模块独立，懒加载，按需创建

## 日志

SDK 使用 Python 标准库 `logging`，logger 名称为 `cloud-space-huawei`：

```python
import logging
logging.getLogger("cloud-space-huawei").setLevel(logging.DEBUG)
```

## License

[MIT](./LICENSE)
