# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-27

### Added

- `ContactsModule` — contacts CRUD, groups, import/export (vCard), avatar upload with auto-crop
- `GalleryModule` — album query/create, file browsing, upload (multipart content), download, favorites, share, recycle bin
- `DriveModule` — file listing, create folder, upload (multipart content), download, move/rename/delete, batch operations
- `FindDeviceModule` — device list, locate, play bell, lost mode, track query, country calling codes
- `PaymentModule` — user grade info, packages, vouchers, client UI config
- `RevisionsModule` — revision rights, version list, retrieve/restore, status query
- Fingerprint module (`fingerprint.py`) — Playwright-based browser fingerprint generation for login
- Heartbeat keep-alive with auto CSRFToken refresh (`start_heartbeat`/`stop_heartbeat`)
- Supplementary portal API: `get_user_space`, `get_family_share_info`, `get_device_and_wallet`, `get_personal_info`, `get_language_map`, `get_client_log_report`, `update_client_log_report`, `data_extract_query_task`, `get_app_info_list_by_consent`, `get_space_banner_config`

### Changed

- **Breaking**: Module access now via lazy-loaded properties (`client.contacts`, `client.gallery`, etc.)
- Improved cookie management with domain-specific cookie routing
- Added `simplify` parameter to portal APIs for cleaner response data
- Unified error handling across all modules (402 auth, 401 expired)

## [0.2.0] - 2026-04-23

### Changed

- **Breaking**: Renamed project from `hwcloud-notepad` to `cloud-space-huawei`
- **Breaking**: Replaced `NotepadClient` with `HuaweiCloudClient` as the main entry point
- Login (`hw_cloud_login`) is now integrated into the SDK via `client.login()` / `client.verify_device()`
- Notepad is now accessed via `client.notepad` (lazy-loaded module)

### Added

- `HuaweiCloudClient` — unified client with login, save/restore, and modular sub-clients
- `AuthManager` — standalone login manager (used internally)
- `LoginResult` dataclass — clean login result with `success`, `need_verify`, `cookies`, `trust_data`
- `HuaweiCloudClient.from_cookies(cookies, trust_data=None)` — create client from cookies dict
- `HuaweiCloudClient.from_cookies(cookies)` — create client from cookies dict without login
- Module skeletons: `contacts`, `gallery`, `drive`, `find_device` (NotImplementedError for now)
- `BaseModule` — shared base class with retry, headers, cookie sync

### Removed

- `NotepadClient` class (replaced by `NotepadModule` via `client.notepad`)
- `hw_cloud_login.py` standalone script (integrated into `auth.py`)

## [0.1.0] - 2025-04-23

### Added

- `NotepadClient` class with unified Huawei Cloud Notepad API
- Tag list, note list, note detail, home data APIs
- Note creation and update support
- Cookie file loading (flat/nested format auto-detection)
- Unified return format `{"ok": bool, "code": str, "msg": str, "data": ...}`
