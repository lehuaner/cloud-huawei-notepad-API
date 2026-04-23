# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
