# 华为云空间 · 版本管理模块使用文档

> ⚠️ **实验性模块**：本模块实现尚不完整，且未经严格测试，可能存在已知或未知的 Bug。如发现确切的 Bug，欢迎提交 [Issue](https://github.com/lehuaner/Cloud-Space-API/issues)。

## 概述

版本管理模块 (`RevisionsModule`) 封装了华为云空间 Web 端版本管理 API，支持查询版本修订权限、获取文件版本列表、恢复文件版本、查询恢复状态等功能。

> **注意**：revisions 系列接口的响应格式与其他模块不同，使用 `result.resultCode` 而非顶层 `code` 字段。

通过 `client.revisions` 访问：

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
    "code": "0",         # 状态码（从 result.resultCode 提取）
    "msg": "版本列表",    # 结果描述
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

## 一、版本修订权限

### 1.1 查询版本修订权限 `query_revision_right()`

查询用户是否具有文件版本管理权限。

```python
result = client.revisions.query_revision_right()

if result.get("ok"):
    data = result["data"]
    right_flag = data["rightFlag"]
    if right_flag == 1:
        print("有版本管理权限")
    else:
        print("无版本管理权限")
```

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `rightFlag` | `int` | 权限标志，`1`=有权限，`0`=无权限 |
| `originData` | `dict` | 原始响应数据 |

---

## 二、版本列表

### 2.1 获取文件版本列表 `get_revisions()`

获取指定服务的版本历史记录。

```python
result = client.revisions.get_revisions(service="addressbook")

if result.get("ok"):
    data_list = result["data"].get("dataList", [])
    for rev in data_list:
        print(f"版本ID: {rev.get('id')}")
        print(f"创建时间: {rev.get('createTime')}")
        print(f"大小: {rev.get('byteSize')} 字节")
        print(f"变更: {rev.get('changeLog')}")
        print(f"条目数: {rev.get('itemCount')}")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `service` | `str` | `"addressbook"` | 服务名（如 `"addressbook"` 通讯录） |

**返回 `data.dataList[]` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 版本ID |
| `createTime` | `int` | 创建时间（毫秒时间戳） |
| `byteSize` | `int` | 数据大小（字节） |
| `channel` | `str` | 操作渠道 |
| `changeLog` | `str` | 变更说明 |
| `itemCount` | `int` | 条目数量 |

---

## 三、版本恢复

### 3.1 恢复文件版本 `retrieve()`

将文件恢复到指定版本。

```python
result = client.revisions.retrieve(
    service="addressbook",
    revision_id="版本ID",
)

if result.get("ok"):
    status = result["data"].get("status", {})
    print(f"恢复操作ID: {status.get('revertId')}")
    print(f"状态: {status.get('status')}")  # 0=进行中, 1=完成
    print(f"创建时间: {status.get('createTime')}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `service` | `str` | 否 | `"addressbook"` | 服务名 |
| `revision_id` | `str` | 否 | `""` | 版本ID（必填，从 `get_revisions()` 的 `dataList` 中获取 `id`） |

> **注意**：`revision_id` 为必填参数，可从 `get_revisions()` 返回的 `dataList` 中获取。

---

### 3.2 获取版本恢复状态 `get_retrieve_status()`

查询文件版本恢复操作的当前状态。

```python
result = client.revisions.get_retrieve_status(
    service="addressbook",
    revert_id="恢复操作ID",  # 从 retrieve() 的 status.revertId 获取
)

if result.get("ok"):
    status = result["data"].get("status", {})
    if status.get("status") == 1:
        print("恢复完成")
    else:
        print("恢复进行中")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `service` | `str` | 否 | `"addressbook"` | 服务名 |
| `revert_id` | `str` | 否 | `""` | 恢复操作ID（由 `retrieve()` 返回的 `status.revertId`） |

**返回 `data.status` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `int` | 恢复状态，`0`=进行中，`1`=完成 |
| `revertId` | `str` | 恢复操作ID |
| `createTime` | `int` | 创建时间 |

---

### 3.3 更新恢复状态 `update_retrieve_status()`

确认文件版本恢复操作已完成，更新恢复状态。

```python
result = client.revisions.update_retrieve_status(
    service="addressbook",
    revision_id="版本ID",
    create_time=1777221351986,
    revert_id="恢复操作ID",
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `service` | `str` | 否 | `"addressbook"` | 服务名 |
| `revision_id` | `str` | 否 | `""` | 版本ID（从 `retrieve()` 的 `status.id` 获取） |
| `create_time` | `int` | 否 | `0` | 恢复操作创建时间（从 `retrieve()` 的 `status.createTime` 获取） |
| `revert_id` | `str` | 否 | `""` | 恢复操作ID（从 `retrieve()` 的 `status.revertId` 获取） |

---

## 四、完整示例

### 4.1 查询权限 → 获取版本 → 恢复

```python
# 1. 检查权限
right = client.revisions.query_revision_right()
if not right.get("ok") or right["data"]["rightFlag"] != 1:
    print("无版本管理权限")
    exit()

# 2. 获取版本列表
revisions = client.revisions.get_revisions(service="addressbook")
if not revisions.get("ok"):
    print("获取版本列表失败")
    exit()

data_list = revisions["data"].get("dataList", [])
if not data_list:
    print("无历史版本")
    exit()

# 3. 选择版本恢复
target = data_list[0]
print(f"恢复版本: {target.get('createTime')}, 条目数: {target.get('itemCount')}")

retrieve_result = client.revisions.retrieve(
    service="addressbook",
    revision_id=target["id"],
)

if not retrieve_result.get("ok"):
    print(f"恢复失败: {retrieve_result['msg']}")
    exit()

# 4. 查询恢复状态
status_data = retrieve_result["data"].get("status", {})
revert_id = status_data.get("revertId", "")

import time
while True:
    status = client.revisions.get_retrieve_status(
        service="addressbook",
        revert_id=revert_id,
    )
    current_status = status["data"].get("status", {}).get("status", 0)
    if current_status == 1:
        print("恢复完成")
        break
    print("恢复中...")
    time.sleep(2)

# 5. 更新恢复状态
client.revisions.update_retrieve_status(
    service="addressbook",
    revision_id=target["id"],
    create_time=status_data.get("createTime", 0),
    revert_id=revert_id,
)
```

---

## 五、API 速查表

| 方法 | 对应接口 | 说明 |
|------|----------|------|
| `query_revision_right()` | `POST /revisions/queryRevisionRight` | 查询版本修订权限 |
| `get_revisions()` | `POST /revisions/getRevisions` | 获取文件版本列表 |
| `retrieve()` | `POST /revisions/retrieve` | 恢复文件版本 |
| `get_retrieve_status()` | `POST /revisions/getRetrieveStatus` | 获取版本恢复状态 |
| `update_retrieve_status()` | `POST /revisions/updateRetrieveStatus` | 更新恢复状态 |
