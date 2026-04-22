# 华为云笔记 API 模块

提供华为云备忘录的基础 HTTP 请求封装。

## 快速开始

```python
from hwcloud_api import api_post, api_get

# 必须传入 cookies 字典
cookies = {"CSRFToken": "...", "userId": "..."}
data = api_post("https://cloud.huawei.com/html/getHomeData", {}, cookies=cookies, verbose=False)
```

## 核心函数

| 函数 | 说明 |
|------|------|
| `api_get(url, cookies, params=None, ...)` | GET 请求，cookies 必须传入 |
| `api_post(url, body, cookies, ...)` | POST 请求，自动注入 traceId |
| `load_cookies(path=None)` | 加载 cookies 文件，返回 `dict` |
| `get_common_headers(cookies)` | 构建请求头，cookies 必须传入 |
| `extract_note_content(data)` | 从响应提取笔记正文 |

## 最佳实践

**1. cookies 必须由调用方从浏览器导出后传入**
```python
# 从浏览器开发者工具 Network 面板复制 cookies.json 内容
cookies = {"CSRFToken": "xxx", "userId": "123", ...}
data = api_post(url, body, cookies=cookies, verbose=False)
```

**2. 使用 `load_cookies()` 加载文件得到 dict，再传入 API**
```python
from hwcloud_api import load_cookies, api_post

cookies = load_cookies("path/to/cookies.json")
data = api_post(url, body, cookies=cookies, verbose=False)
```

**3. 生产环境关闭 verbose**
```python
data = api_post(url, body, cookies=cookies, verbose=False)
```

**4. 响应状态码 200 不代表业务成功，需检查 `code` 字段**
```python
data = api_post(url, body, cookies=cookies, verbose=False)
if data and data.get("code") == "0":
    # 业务成功
    pass
```

**5. 401 表示 cookies 过期，需重新从浏览器导出**

**6. 使用 `output_file` 保存调试响应**
```python
data = api_post(url, body, cookies=cookies, output_file="response.json")
```

## Cookies 格式

传入格式为 `dict`：

```python
{"CSRFToken": "xxx", "userId": "123", ...}
```

`load_cookies()` 兼容两种文件格式（自动转换）：
- 扁平：`{"CSRFToken": "xxx"}`
- 嵌套：`{"CSRFToken": {"value": "xxx", "domain": "..."}}`
