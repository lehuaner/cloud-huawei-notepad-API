# Cloud Space API

A Python SDK for Cloud Space, providing login, notepad, contacts, gallery, drive, find device, payment, and revisions APIs.

[中文文档](./README.md)

## ⚠️ Disclaimer

**This project is for educational and research purposes only.** Any commercial or illegal use is strictly prohibited. This is an **unofficial** project and is not affiliated with Huawei Technologies Co., Ltd. Please read the [full disclaimer](./docs/DISCLAIMER.md) before using this project.

## Installation

```bash
git clone https://github.com/lehuaner/Cloud-Space-API.git
cd Cloud-Space-API
pip install -e .
```

Requirements: Python >= 3.8, `requests >= 2.28`

## Quick Start

### 1. Login with phone and password

```python
from cloud_space_huawei import HuaweiCloudClient

client = HuaweiCloudClient()
result = client.login("phone", "password")

if result.need_verify:
    code = input("Verification code: ")
    result = client.verify_device(code)

if result:
    # Save cookies — they contain trust info for skipping verification next time
    cookies = result.cookies
    print(f"Login success! userId={cookies.get('userId')}")
```

### 2. Restore session from cookies

```python
from cloud_space_huawei import HuaweiCloudClient

# Create from saved cookies
client = HuaweiCloudClient.from_cookies(cookies)
```

### 3. Skip device verification with saved cookies

```python
from cloud_space_huawei import HuaweiCloudClient

client = HuaweiCloudClient()

# Pass saved cookies to skip device verification
result = client.login("phone", "password", cookies=cookies)
```

### 4. Use the notepad module

```python
# List notes
result = client.notepad.get_notes_list()
if result["ok"]:
    for note in result["data"]["noteList"]:
        print(f"Note: {note.get('title', '')} (GUID: {note['guid']})")

# Create a note
result = client.notepad.create_note(title="Title", content_text="Content")
if result["ok"]:
    client.notepad.sync()

# Update a note
result = client.notepad.update_note(guid="guid", etag="1", title="New", content_text="New content")
if result["ok"]:
    client.notepad.sync()
```

### 5. Use other modules

```python
# Contacts
client.contacts.get_contacts()
client.contacts.create_contact({"name": "Zhang San", "phone": "13800138000"})

# Gallery
client.gallery.get_stat_info()
client.gallery.query_albums()
client.gallery.get_files(album_id="default-album-1")

# Drive
client.drive.list_files()
client.drive.upload_file("photo.jpg")
client.drive.download_file(file_id="xxx", save_path="photo.jpg")

# Find Device
client.find_device.get_device_list()
client.find_device.locate(device_id="xxx", device_type=9)
client.find_device.play_bell(device_id="xxx", device_type=9)

# Payment ⚠️
client.payment.get_user_grade_info()
client.payment.get_available_grade_packages()

# Revisions ⚠️
client.revisions.query_revision_right()
client.revisions.get_revisions(service="addressbook")
```

### 6. Heartbeat keep-alive

```python
client = HuaweiCloudClient.from_cookies(cookies)

# Start background heartbeat thread (auto-refresh CSRFToken)
client.start_heartbeat(interval=300)

# Get the latest CSRFToken at any time
token = client.csrf_token

# Stop heartbeat
client.stop_heartbeat()
```

### 7. Direct session access

```python
# The underlying requests.Session is fully exposed
resp = client._session.get("https://cloud.huawei.com/some-api")
print(resp.json())

# Manual cookie management
cookies = client.cookies
```

## API Reference

### Core Client `HuaweiCloudClient`

#### Login API

| Method | Description |
|--------|-------------|
| `login(phone, password, cookies=None)` | Login with phone/password, returns `LoginResult` |
| `send_verify_code(device_index=0)` | Get verification device list (triggers server to send code) |
| `verify_device(verify_code)` | Submit device verification code |
| `from_cookies(cookies)` | Class method, restore session from cookies dict |
| `logout()` | Logout from Huawei Cloud Space |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `cookies` | `dict` | Current cookies dict (synced from session) |
| `need_verify` | `bool` | Whether current session needs device trust verification |
| `csrf_token` | `str` | Current latest CSRFToken (auto-refreshed by heartbeat) |
| `heartbeat_running` | `bool` | Whether heartbeat thread is running |
| `notepad` | `NotepadModule` | Notepad module |
| `contacts` | `ContactsModule` | Contacts module |
| `gallery` | `GalleryModule` | Gallery module |
| `drive` | `DriveModule` | Drive module |
| `find_device` | `FindDeviceModule` | Find device module |
| `payment` | `PaymentModule` | Payment module ⚠️ |
| `revisions` | `RevisionsModule` | Revisions module ⚠️ |

#### Heartbeat

| Method | Description |
|--------|-------------|
| `start_heartbeat(interval=300, on_csrf_refresh=None)` | Start background heartbeat thread |
| `stop_heartbeat()` | Stop background heartbeat thread |

#### Portal API

| Method | Description |
|--------|-------------|
| `get_common_param(simplify=True)` | Get common parameters |
| `get_home_data(simplify=True)` | Get home data (includes deviceIdForHeader) |
| `get_cookies()` | Query server-side Cookie values |
| `heartbeat_check()` | Heartbeat check, keep session alive |
| `notify_poll(tag, module, timeout)` | Notification polling (long polling) |
| `get_space_info(simplify=True)` | Get cloud space capacity info |
| `refresh_cookies()` | Refresh cookies and update client state |

#### Supplementary API

| Method | Description |
|--------|-------------|
| `get_user_space()` | Get user space details |
| `get_family_share_info()` | Get family share info |
| `get_device_and_wallet()` | Get device and wallet info |
| `get_personal_info()` | Get personal info |
| `get_language_map()` | Get language map |
| `get_client_log_report()` | Get client log report config |
| `update_client_log_report(log_data)` | Update client log report |
| `data_extract_query_task()` | Query data extract task |
| `get_app_info_list_by_consent()` | Get app data management info |
| `get_space_banner_config()` | Get cloud space banner config |

### `LoginResult`

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether successful |
| `need_verify` | `bool` | Whether secondary verification is needed |
| `cookies` | `dict` | Post-login cookies (contains trust device info) |
| `auth_devices` | `list` | Verification device list |
| `error` | `str` | Error message |

### Submodule Documentation

| Module | Documentation |
|--------|--------------|
| Contacts `ContactsModule` | [docs/contacts.md](docs/contacts.md) |
| Gallery `GalleryModule` | [docs/gallery.md](docs/gallery.md) |
| Drive `DriveModule` | [docs/drive.md](docs/drive.md) |
| Notepad `NotepadModule` | [docs/notepad.md](docs/notepad.md) |
| Find Device `FindDeviceModule` | [docs/find_device.md](docs/find_device.md) |
| Payment `PaymentModule` ⚠️ | [docs/payment.md](docs/payment.md) |
| Revisions `RevisionsModule` ⚠️ | [docs/revisions.md](docs/revisions.md) |

### Unified Return Format

All submodule methods return:

```python
{
    "ok": bool,       # Whether the operation succeeded
    "code": str,      # Status code, "0" means success
    "msg": str,       # Human-readable message
    "data": ...       # Specific data
}
```

## ⚠️ Experimental Modules

The `payment` and `revisions` modules are **incomplete and not thoroughly tested**. They may contain known or unknown bugs. Please note:

- Some APIs may not work correctly or return unexpected data
- API parameters and return formats may change in future versions
- If you find a confirmed bug, please submit an [Issue](https://github.com/lehuaner/Cloud-Space-API/issues)

## Design Principles

1. **Simple**: `HuaweiCloudClient` is the single entry point, login to use all modules
2. **User-controlled**: `cookies` are fully managed by users, SDK makes no storage assumptions
3. **Freedom**: Underlying `requests.Session` is fully exposed for custom requests
4. **Modular**: Each feature module is independent and lazy-loaded

## Logging

SDK uses Python standard `logging`, logger name is `cloud-space-huawei`:

```python
import logging
logging.getLogger("cloud-space-huawei").setLevel(logging.DEBUG)
```

## License

[MIT](./LICENSE)
