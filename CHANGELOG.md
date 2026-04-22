# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-04-23

### Added

- `NotepadClient` 类，统一封装华为云备忘录 API
- 支持获取标签列表、笔记列表、笔记详情、首页数据
- 支持创建和更新笔记
- 支持 cookies 从文件加载（兼容扁平/嵌套格式）
- 统一返回格式 `{"ok": bool, "code": str, "msg": str, "data": ...}`
