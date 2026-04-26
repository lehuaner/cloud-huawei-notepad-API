# 华为云空间 · 会员/支付模块使用文档

> ⚠️ **实验性模块**：本模块实现尚不完整，且未经严格测试，可能存在已知或未知的 Bug。如发现确切的 Bug，欢迎提交 [Issue](https://github.com/lehuaner/Cloud-Space-API/issues)。

## 概述

会员/支付模块 (`PaymentModule`) 封装了华为云空间 Web 端会员和支付相关 API，支持查询用户等级、套餐信息、可用套餐列表、优惠券等功能。

通过 `client.payment` 访问：

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
    "msg": "用户等级信息", # 结果描述
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

## 一、用户等级信息

### 1.1 获取用户等级信息 `get_user_grade_info()`

获取当前用户的会员等级、有效期等信息。

```python
result = client.payment.get_user_grade_info()

if result.get("ok"):
    data = result["data"]
    print(f"等级: {data['gradeName']}")
    print(f"等级代码: {data['gradeCode']}")
    print(f"等级状态: {data['gradeState']}")
    print(f"有效期至: {data['validToTime']}")
    print(f"自动续费: {data['autoRenew']}")
```

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `gradeCode` | `str` | 等级代码 |
| `gradeState` | `int` | 等级状态 |
| `validToTime` | `int` | 有效期截止时间（毫秒时间戳） |
| `hexCode` | `str` | 十六进制等级代码 |
| `autoRenew` | `int` | 是否自动续费 |
| `gradeName` | `str` | 等级名称 |
| `gradeDesc` | `str` | 等级描述 |
| `originData` | `dict` | 原始响应数据 |

---

## 二、套餐信息

### 2.1 获取用户套餐 `get_user_package()`

获取用户当前购买的云空间套餐详情。

```python
result = client.payment.get_user_package()

if result.get("ok"):
    data = result["data"]
    print(f"套餐: {data.get('packageName', '')}")
    print(f"容量: {data.get('packageSize', 0)}")
```

---

### 2.2 获取可用套餐列表 `get_available_grade_packages()`

获取所有可购买的云空间套餐，包含价格、容量等信息。

```python
result = client.payment.get_available_grade_packages()

if result.get("ok"):
    print(f"可用套餐: {result['data']}")
```

---

## 三、优惠券

### 3.1 获取可用优惠券 `get_ava_vouchers()`

获取用户当前可用的优惠券列表。

```python
result = client.payment.get_ava_vouchers()

if result.get("ok"):
    vouchers = result["data"].get("voucherList", [])
    for v in vouchers:
        print(f"优惠券: {v}")
```

---

## 四、UI 配置

### 4.1 获取客户端 UI 配置 `get_client_ui_config()`

获取支付相关的 UI 配置信息，如价格展示、购买按钮文案等。

```python
result = client.payment.get_client_ui_config()
```

---

## 五、API 速查表

| 方法 | 对应接口 | 说明 |
|------|----------|------|
| `get_user_grade_info()` | `POST /payment/getUserGradeInfo` | 获取用户等级信息 |
| `get_user_package()` | `POST /payment/getUserPackage` | 获取用户套餐信息 |
| `get_available_grade_packages()` | `POST /payment/getAvailableGradePackages` | 获取可购买套餐列表 |
| `get_ava_vouchers()` | `POST /payment/getAvaVouchers` | 获取可用优惠券 |
| `get_client_ui_config()` | `POST /payment/getClientUIConfig` | 获取客户端 UI 配置 |
