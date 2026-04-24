# cloud-space-huawei

A Python SDK for Huawei Cloud Space (华为云空间), providing login, notepad, contacts, gallery, drive, and find device APIs.

[中文文档](./README.md)

## Installation

```bash
git clone https://github.com/your-repo/cloud-space-huawei.git
cd cloud-space-huawei
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

### 5. Direct session access

```python
# The underlying requests.Session is fully exposed
resp = client.session.get("https://cloud.huawei.com/some-api")
print(resp.json())
```

## API Reference

### Core Client `HuaweiCloudClient`

| Method | Description |
|--------|-------------|
| `login(phone, password, cookies=None)` | Login with phone/password, returns `LoginResult` |
| `verify_device(verify_code)` | Submit device verification code |
| `from_cookies(cookies)` | Class method, restore session from cookies dict |
| `get_home_data(simplify=True)` | Get home data (includes deviceIdForHeader), simplified when simplify=True |
| `get_space_info(simplify=True)` | Get space info, simplified when simplify=True |
| `get_common_param(simplify=True)` | Get common parameters, simplified when simplify=True |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `cookies` | `dict` | Current cookies dict |
| `notepad` | `NotepadModule` | Notepad module |
| `contacts` | `ContactsModule` | Contacts module (skeleton) |
| `gallery` | `GalleryModule` | Gallery module (skeleton) |
| `drive` | `DriveModule` | Drive module (skeleton) |
| `find_device` | `FindDeviceModule` | Find device module (skeleton) |

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

### Notepad `NotepadModule`

| Method | Description |
|--------|-------------|
| `get_tags(simplify=True)` | Get tag list, simplified when simplify=True |
| `get_notes_list(index, status, guids, simplify=True)` | Get notes list, simplified when simplify=True |
| `get_note_detail(guid, kind, start_cursor)` | Get note detail |
| `create_note(title, content_text, tag_id)` | Create a new note |
| `update_note(guid, etag, title, content_text, ...)` | Update a note |
| `sync(ctag_note_info, ctag_task_info, start_cursor)` | Sync operation |
| `get_task_detail(guid, ctag_task_info, start_cursor)` | Query task detail |
| `get_graffiti_data(asset_id, record_id, version_id, kind)` | Get graffiti data |
| `pre_process_file(need_to_sign_url, http_method, generate_sign_flag)` | File pre-signing |

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

## Design Principles

1. **Simple**: `HuaweiCloudClient` is the single entry point
2. **User-controlled**: `cookies` are fully managed by users
3. **Modular**: Each feature module is independent and lazy-loaded

## License

[MIT](./LICENSE)
