# 华为云空间 · 查找设备模块使用文档

## 概述

查找设备模块 (`FindDeviceModule`) 封装了华为云空间 Web 端查找设备 API，支持设备列表查询、定位、响铃、丢失模式管理、轨迹查询等功能。

通过 `client.find_device` 访问：

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
    "msg": "2个设备",     # 结果描述
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

## 一、基础信息

### 1.1 获取首页数据 `get_home_data()`

获取查找设备首页配置信息，如地图 API URL、超时设置、用户信息等。

```python
result = client.find_device.get_home_data()

if result.get("ok"):
    data = result["data"]
    print(f"地图API: {data['amapUrl']}")
    print(f"用户名: {data['accountName']}")
    print(f"响铃超时(在线): {data['bellTimeoutForMain']}秒")
    print(f"响铃超时(离线): {data['bellTimeoutForMainOffline']}秒")
```

**返回 `data` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `userName` | `str` | 用户名 |
| `accountName` | `str` | 账号名 |
| `userEmail` | `str` | 用户邮箱 |
| `secretPhone` | `str` | 加密手机号 |
| `countryCode` | `str` | 国家代码 |
| `lang` | `str` | 语言 |
| `hwMapKey` | `str` | 华为地图 Key |
| `hwMapRestApiUrl` | `str` | 华为地图 API URL |
| `hwMapStaticUrl` | `str` | 华为地图静态图 URL |
| `amapUrl` | `str` | 高德地图 URL |
| `amapWebapiUrl` | `str` | 高德地图 Web API URL |
| `serverTime` | `int` | 服务器时间 |
| `bellTimeoutForMain` | `int` | 在线设备响铃超时（秒） |
| `bellTimeoutForMainOffline` | `int` | 离线设备响铃超时（秒） |
| `locateUpdateTime` | `int` | 定位更新时间（秒） |
| `enableShare` | `int` | 是否启用分享 |
| `enableOfflineLocation` | `int` | 是否启用离线定位 |

---

### 1.2 获取用户信息 `get_user_info()`

获取用户信息（简化版）。

```python
result = client.find_device.get_user_info()

if result.get("ok"):
    print(f"用户名: {result['data']['userName']}")
    print(f"头像: {result['data']['userImg']}")
```

---

### 1.3 获取分享授权信息 `get_share_grant_info()`

获取设备位置的分享授权信息。

```python
result = client.find_device.get_share_grant_info()
```

---

## 二、设备列表

### 2.1 获取设备列表 `get_device_list()`

获取当前账号下的所有设备列表。

```python
result = client.find_device.get_device_list()

if result.get("ok"):
    for device in result["data"]["deviceList"]:
        print(f"设备: {device['deviceAliasName']}")
        print(f"  类型: {device['deviceTypeName']}")
        print(f"  在线: {device['offlineStatus'] == 1}")
        print(f"  可定位: {device['canLocate']}")
        print(f"  可响铃: {device['canBell']}")
        print(f"  可锁定: {device['canLock']}")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tab_location` | `int` | `2` | 选项卡位置，`2` = 全部设备 |

**返回 `data.deviceList[]` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `deviceId` | `str` | 设备ID |
| `deviceAliasName` | `str` | 设备别名 |
| `deviceType` | `int` | 设备类型编号 |
| `deviceTypeName` | `str` | 设备类型名称（手机/平板/手表/配件） |
| `deviceCategory` | `str` | 设备分类（phone/pad） |
| `capability` | `List[str]` | 设备能力列表 |
| `offlineStatus` | `int` | 在线状态，`1` = 在线 |
| `canLocate` | `bool` | 是否可定位 |
| `canBell` | `bool` | 是否可响铃 |
| `canLock` | `bool` | 是否可锁定 |
| `canLostPattern` | `bool` | 是否可开启丢失模式 |
| `canClear` | `bool` | 是否可擦除 |
| `canTrackReport` | `bool` | 是否可查询轨迹 |
| `locateResult` | `dict` | 定位结果（如有） |

---

### 2.2 根据名称查找设备 `get_device_by_name()`

按设备名称模糊匹配查找设备。

```python
result = client.find_device.get_device_by_name("Mate")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | 是 | 设备名称（模糊匹配） |

---

### 2.3 获取在线设备 `get_online_devices()`

获取当前在线的设备列表。

```python
result = client.find_device.get_online_devices()
```

---

### 2.4 获取可定位设备 `get_locatable_devices()`

获取支持定位功能的设备列表。

```python
result = client.find_device.get_locatable_devices()
```

---

## 三、设备定位

### 3.1 发起定位 `locate()`

向设备发送定位请求。

```python
result = client.find_device.locate(
    device_id="xxx",
    device_type=9,  # 9=手机, 2=平板
)

if result.get("ok"):
    print("定位请求已发送")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `device_id` | `str` | 是 | — | 设备ID |
| `device_type` | `int` | 否 | `9` | 设备类型，`9`=手机，`2`=平板 |
| `per_device_type` | `str` | 否 | `"0"` | 配件类型，`"0"`=主设备 |
| `cpt_list` | `str` | 否 | `""` | 配件列表 |
| `endpoint_crypted` | `str` | 否 | `"1"` | 是否端到端加密 |

---

### 3.2 查询定位结果 `query_locate_result()`

查询设备定位的结果，包含经纬度、电池、网络等信息。

```python
result = client.find_device.query_locate_result(
    device_id="xxx",
    device_type=9,
)

if result.get("ok"):
    data = result["data"]
    locate_info = data.get("locateInfo", {})
    coord = locate_info.get("coordinate", {})
    print(f"纬度: {coord.get('latitude')}")
    print(f"经度: {coord.get('longitude')}")
    print(f"精度: {coord.get('accuracy')}")
    battery = locate_info.get("battery", {})
    print(f"电量: {battery.get('percentage')}%")
    print(f"充电中: {battery.get('isCharging') == '1'}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `device_id` | `str` | 是 | — | 设备ID |
| `device_type` | `int` | 否 | `9` | 设备类型 |
| `per_device_type` | `str` | 否 | `"0"` | 配件类型 |
| `sequence` | `int` | 否 | `0` | 查询序列号 |
| `endpoint_crypted` | `str` | 否 | `"1"` | 是否端到端加密 |

---

## 四、响铃

### 4.1 播放铃声 `play_bell()`

播放设备铃声。推荐开启 `auto_locate`，会先定位唤醒设备以提高成功率。

```python
result = client.find_device.play_bell(
    device_id="xxx",
    device_type=9,
    auto_locate=True,     # 先定位唤醒设备
    locate_retry=3,       # 定位重试次数
    locate_wait=1.5,      # 定位后等待秒数
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `device_id` | `str` | 是 | — | 设备ID |
| `device_type` | `int` | 否 | `9` | 设备类型 |
| `per_device_type` | `str` | 否 | `"0"` | 配件类型 |
| `cpt_list` | `str` | 否 | `""` | 配件列表 |
| `auto_locate` | `bool` | 否 | `True` | 是否先定位唤醒设备（推荐开启） |
| `locate_retry` | `int` | 否 | `3` | 定位重试次数 |
| `locate_wait` | `float` | 否 | `1.5` | 定位后等待秒数 |

---

### 4.2 完整响铃流程 `ring_device()`

一站式响铃接口，封装了完整的检查与响铃流程：

1. 检查设备是否存在
2. 检查设备是否支持响铃
3. 检查设备在线状态
4. 发起定位唤醒
5. 轮询等待设备响应
6. 发送响铃请求
7. 确认响铃结果

```python
result = client.find_device.ring_device(
    device_id="xxx",
    device_type=9,
    max_wait_time=30,       # 最大等待设备响应时间（秒）
    check_interval=2.0,     # 轮询检查间隔（秒）
)

if result.get("ok"):
    print(result["msg"])
    data = result["data"]
    print(f"定位尝试: {data.get('locate_attempts')}次")
    print(f"总耗时: {data.get('total_time')}秒")
else:
    print(f"响铃失败: {result['msg']}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `device_id` | `str` | 是 | — | 设备ID |
| `device_type` | `int` | 否 | `9` | 设备类型 |
| `max_wait_time` | `int` | 否 | `30` | 最大等待设备响应时间（秒） |
| `check_interval` | `float` | 否 | `2.0` | 轮询检查间隔（秒） |

---

### 4.3 查询响铃结果 `query_bell_result()`

查询响铃请求的执行结果。

```python
result = client.find_device.query_bell_result(
    device_id="xxx",
    device_type=9,
)
```

---

## 五、丢失模式

### 5.1 开启丢失模式 `start_lost_mode()`

开启丢失模式，锁定设备并显示留言和联系电话。

```python
result = client.find_device.start_lost_mode(
    device_id="xxx",
    device_type=9,
    message="这是我的设备，请归还",
    phone_num="+86138****8888",
    email="my@email.com",
    country_calling_code="+86",
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `device_id` | `str` | 是 | — | 设备ID |
| `device_type` | `int` | 否 | `9` | 设备类型 |
| `message` | `str` | 否 | `""` | 留言信息 |
| `phone_num` | `str` | 否 | `""` | 联系电话（含国家码格式，如 `+86138****8888`） |
| `email` | `str` | 否 | `""` | 联系邮箱 |
| `lock_screen` | `str` | 否 | `""` | 锁屏密码 |
| `lock_sdcard` | `str` | 否 | `""` | 锁定 SD 卡密码 |
| `country_calling_code` | `str` | 否 | `"+86"` | 国际区号 |
| `endpoint_crypted` | `str` | 否 | `"1"` | 是否端到端加密 |
| `is_notify_change` | `bool` | 否 | `True` | 是否通知变更（首次开启设为 True，修改时设为 False） |

**错误码：**

| 错误码 | 说明 |
|--------|------|
| `010001` | 手机号格式错误 |
| `010002` | 设备不支持丢失模式 |
| `010003` | 设备离线 |

---

### 5.2 关闭丢失模式 `stop_lost_mode()`

关闭丢失模式，解锁设备。

```python
result = client.find_device.stop_lost_mode(
    device_id="xxx",
    device_type=9,
)
```

---

### 5.3 查询丢失模式信息 `query_lost_mode_info()`

查询当前丢失模式的配置信息。

```python
result = client.find_device.query_lost_mode_info(
    device_id="xxx",
    device_type=9,
)

if result.get("ok"):
    data = result["data"]
    print(f"留言: {data['message']}")
    print(f"联系电话: {data['phoneNum']}")
    print(f"已开启: {data['openLostPattern']}")
```

---

### 5.4 查询命令执行结果 `query_cmd_result()`

查询设备命令执行结果（如清除数据、锁定屏幕等）。

```python
result = client.find_device.query_cmd_result(
    device_id="xxx",
    device_type=9,
    cmds=["openLostPattern", "stopLostPattern", "clear"],
)
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `device_id` | `str` | 是 | — | 设备ID |
| `device_type` | `int` | 否 | `9` | 设备类型 |
| `cmds` | `List[str]` | 否 | `["openLostPattern", "stopLostPattern", "clear"]` | 要查询的命令列表 |
| `per_device_type` | `str` | 否 | `"0"` | 配件类型 |

---

## 六、轨迹查询

### 6.1 查询设备轨迹 `query_tracks()`

查询设备的历史位置轨迹。

```python
result = client.find_device.query_tracks(
    device_id="xxx",
    device_type=9,
)

if result.get("ok"):
    for track in result["data"]["tracks"]:
        coord = track.get("coordinate", {})
        print(f"时间: {track['createTime_str']}")
        print(f"纬度: {coord.get('latitude')}, 经度: {coord.get('longitude')}")
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `device_id` | `str` | 是 | — | 设备ID |
| `device_type` | `int` | 否 | `9` | 设备类型 |
| `origin_info` | `dict` | 否 | `{}` | 起始信息 |
| `execute_time` | `int` | 否 | `0` | 执行时间 |
| `track_type` | `int` | 否 | `1` | 轨迹类型，`1`=当前位置 |
| `endpoint_crypted` | `str` | 否 | `"1"` | 是否端到端加密 |

---

## 七、其他

### 7.1 查询国际区号列表 `query_country_calling_code()`

查询支持的国家/地区代码映射。

```python
result = client.find_device.query_country_calling_code()

if result.get("ok"):
    print(f"默认区号: {result['data']['defaultCallingCode']}")
    print(f"支持 {len(result['data']['countryMap'])} 个国家/地区")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `lang` | `str` | `"zh-cn"` | 语言代码 |

---

### 7.2 上报地图健康状态 `report_map_health()`

上报地图加载的健康状态。

```python
result = client.find_device.report_map_health()
```

---

## 八、API 速查表

| 方法 | 对应接口 | 说明 |
|------|----------|------|
| `get_home_data()` | `POST /findDevice/getHomeData` | 获取首页数据 |
| `get_user_info()` | `POST /findDevice/getInfos` | 获取用户信息 |
| `get_share_grant_info()` | `POST /findDevice/getShareGrantInfo` | 获取分享授权信息 |
| `get_device_list()` | `POST /findDevice/getMobileDeviceList` | 获取设备列表 |
| `locate()` | `POST /findDevice/locate` | 发起定位 |
| `query_locate_result()` | `POST /findDevice/queryLocateResult` | 查询定位结果 |
| `play_bell()` | `POST /findDevice/portalBellReq` | 播放铃声 |
| `ring_device()` | 多步流程 | 完整响铃流程 |
| `query_bell_result()` | `POST /findDevice/queryportalBellReqResult` | 查询响铃结果 |
| `start_lost_mode()` | `POST /findDevice/startLostPattern` | 开启丢失模式 |
| `stop_lost_mode()` | `POST /findDevice/stopLostPattern` | 关闭丢失模式 |
| `query_lost_mode_info()` | `POST /findDevice/queryopenPatternParInfo` | 查询丢失模式信息 |
| `query_cmd_result()` | `POST /findDevice/getCmdResult` | 查询命令执行结果 |
| `query_tracks()` | `POST /findDevice/queryTracksList` | 查询设备轨迹 |
| `query_country_calling_code()` | `POST /findDevice/queryCountryCallingCode` | 查询国际区号列表 |
| `report_map_health()` | `POST /findDevice/reportMapHealth` | 上报地图健康状态 |
| `get_device_by_name()` | `get_device_list` + 筛选 | 根据名称查找设备 |
| `get_online_devices()` | `get_device_list` + 筛选 | 获取在线设备 |
| `get_locatable_devices()` | `get_device_list` + 筛选 | 获取可定位设备 |
