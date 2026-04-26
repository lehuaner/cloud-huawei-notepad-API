# 华为云空间 · 联系人模块使用文档

## 概述

联系人模块 (`ContactsModule`) 封装了华为云空间 Web 端全部联系人 API，支持联系人的增删改查、群组管理、导入导出、头像上传等功能。

通过 `client.contacts` 访问：

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
    "result": {...},      # 服务端返回的 result 对象
    "data": ...          # 具体数据（视接口而定）
}
```

失败时：

```python
{
    "ok": False,
    "error": "错误描述",
    "_code": "401"       # 错误码
}
```

---

## 一、联系人查询

### 1.1 获取全部联系人 `get_contacts()`

获取所有联系人列表。

```python
result = client.contacts.get_contacts()

# 获取回收站中的联系人
result = client.contacts.get_contacts(soft_del="1")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `soft_del` | `str` | `"0"` | `"0"` = 正常联系人，`"1"` = 回收站中的联系人 |

---

### 1.2 分页查询联系人 `query_contacts_by_page()`

分页获取联系人列表。

```python
result = client.contacts.query_contacts_by_page()

# 查询回收站
result = client.contacts.query_contacts_by_page(soft_del="1")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `soft_del` | `str` | `"0"` | `"0"` = 正常联系人，`"1"` = 回收站中的联系人 |

---

### 1.3 获取指定联系人详情 `get_design_contact()`

根据联系人ID列表获取详细资料。

```python
result = client.contacts.get_design_contact(
    contact_ids=["FsuGCA_OIZMv7kAS8BI9Pqbv9m70QiG3L"]
)

if result.get("ok"):
    for contact in result.get("data", []):
        print(f"姓名: {contact.get('name', {}).get('firstName', '')}")
        print(f"电话: {[t['value'] for t in contact.get('telList', [])]}")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `contact_ids` | `List[str]` | 是 | 联系人ID列表 |

---

## 二、联系人创建与更新

### 2.1 简化字典字段映射

创建和更新联系人时，传入**简化字典**即可自动解析为 API 请求体格式：

| 简化字段 | API 字段 | 说明 |
|----------|----------|------|
| `name` | `name.firstName` | 名 |
| `last_name` | `name.lastName` | 姓 |
| `middle_name` | `name.middleName` | 中间名 |
| `prefix` | `name.namePrefix` | 姓名前缀 |
| `suffix` | `name.nameSuffix` | 姓名后缀 |
| `phone` | `telList` | 电话号码（str 或 list） |
| `email` | `emailList` | 邮箱（str 或 list） |
| `im` | `msgList` | 即时通讯（str 或 list） |
| `org` | `organizeList` | 工作单位（str / dict / list） |
| `address` | `addressList` | 地址（str / dict / list） |
| `url` | `urlList` | 网站（str 或 list） |
| `date` | `dateList` | 日期（str 或 list） |
| `event` | `eventList` | 事件（str 或 list） |
| `relation` | `relationList` | 关系（str 或 list） |
| `nickname` | `nickName` | 昵称（仅电脑端可见，手机端不显示） |
| `note` | `note` | 备注 |
| `birthday` | `bDay` + `dateList` | 公历生日（自动设置 bDay 和 dateList type=1） |
| `birthday_lunar` | `dateList` + `bDayLunar` | 农历生日（自动设置 dateList type=2，服务端填充 bDayLunar） |
| `photo` | `photoUrl` | 头像（支持文件路径 / Base64 / dict，详见头像章节） |
| `contact_id` | `contactId` | 联系人ID（更新时必填） |
| `uid` | `uId` | 联系人UID |
| `groups` | `groupIdList` + `groupName` | 群组（仅电脑端可见，手机端不显示） |
| `group_ids` | `groupIdList` | 群组ID列表（仅电脑端可见，手机端不显示） |
| `group_names` | `groupName` | 群组名称列表（仅电脑端可见，手机端不显示） |

> **注意**：
> - 未识别的 key 会原样保留，可用于直接传递 API 原始字段。
> - `birthday` 和 `birthday_lunar` 的值格式相同（如 `"2003-08-23"`），区别仅在于 `dateList` 的 `type`：公历为 `type=1`，农历为 `type=2`。手机端会自动将农历日期转换为对应的公历日期来显示和提醒。
> - **昵称（nickname）和群组（groups）仅在电脑端云空间可见，手机端不显示。**

---

### 2.2 创建联系人 `create_contact()`

```python
# ── 1. 最小创建：仅姓名 ──
result = client.contacts.create_contact({"name": "最小联系人"})
print("最小创建:", "ok" if result.get("ok") else result.get("error"))

# ── 2. 最大创建：所有字段 + 所有 type 枚举值 + 头像 + 群组 ──
result = client.contacts.create_contact({
    # ── 姓名（5 个子字段） ──
    "name":        "最大",
    "last_name":   "联系人",
    "middle_name": "中",
    "prefix":      "Mr.",
    "suffix":      "Jr.",

    # ── 电话：覆盖全部 9 种 type ──
    "phone": [
        {"type": 1, "value": "13800138000"},              # 手机
        {"type": 2, "value": "010-12345678"},             # 住宅
        {"type": 3, "value": "021-87654321"},             # 单位
        {"type": 14, "value": "010-99998888"},            # 总机
        {"type": 5, "value": "010-11112222"},             # 单位传真
        {"type": 6, "value": "010-33334444"},             # 住宅传真
        {"type": 7, "value": "010-55556666"},             # 寻呼机
        {"type": 8, "value": "010-77778888"},             # 其它
        {"type": 0, "value": "13900139000", "name": "副号"},  # 自定义
    ],

    # ── 邮箱：覆盖全部 4 种 type ──
    "email": [
        {"type": 1, "value": "personal@example.com"},     # 私人
        {"type": 2, "value": "work@company.com"},         # 单位
        {"type": 3, "value": "other@example.com"},        # 其它
        {"type": 0, "value": "custom@example.com", "name": "备用"},  # 自定义
    ],

    # ── 即时通讯：覆盖全部 9 种 type ──
    "im": [
        {"type": 1, "value": "my_aim"},                   # AIM
        {"type": 2, "value": "my_live@live.com"},         # Windows Live
        {"type": 3, "value": "my_yahoo"},                 # 雅虎
        {"type": 4, "value": "my_skype"},                 # Skype
        {"type": 5, "value": "123456789"},                # QQ
        {"type": 6, "value": "my_hangout@gmail.com"},     # 环聊
        {"type": 7, "value": "123456789"},                # ICQ
        {"type": 8, "value": "my_jabber@jabber.org"},     # Jabber
        {"type": 0, "value": "my_custom_im", "name": "飞书"},  # 自定义
    ],

    # ── 地址：覆盖全部 4 种 type ──
    "address": [
        {"type": 1, "street": "北京市朝阳区xx路1号"},      # 住宅
        {"type": 2, "street": "深圳市龙岗区xx基地"},       # 单位
        {"type": 3, "street": "上海市浦东新区xx街"},       # 其它
        {"type": 0, "street": "广州市天河区xx大道", "name": "宿舍"},  # 自定义
    ],

    # ── 日期：type=3 周年纪念, type=4 其它重要日期 ──
    # 注意: type=1(公历生日) 通过 birthday 字段设置，type=2(农历生日) 通过 birthday_lunar 设置
    "date": [
        {"type": 3, "value": "2005-09-01"},               # 周年纪念
        {"type": 4, "value": "2020-03-08"},               # 其它重要日期
    ],

    # ── 网站：无 type/name，仅 value ──
    "url": [
        {"value": "www.example.com"},
        {"value": "blog.example.com"},
        {"value": "github.com/example"},
    ],

    # ── 关系：覆盖全部 15 种 type ──
    "relation": [
        {"type": 1,  "value": "赵一"},    # 助理
        {"type": 2,  "value": "钱二"},    # 弟兄
        {"type": 3,  "value": "孙三"},    # 子女
        {"type": 4,  "value": "李四"},    # 合作伙伴
        {"type": 5,  "value": "周五"},    # 父亲
        {"type": 6,  "value": "吴六"},    # 朋友
        {"type": 7,  "value": "郑七"},    # 上司
        {"type": 8,  "value": "王八"},    # 母亲
        {"type": 9,  "value": "冯九"},    # 父母
        {"type": 10, "value": "陈十"},    # 伴侣
        {"type": 11, "value": "褚十一"},  # 介绍人
        {"type": 12, "value": "卫十二"},  # 亲属
        {"type": 13, "value": "蒋十三"},  # 姐妹
        {"type": 14, "value": "沈十四"},  # 配偶
        {"type": 0,  "value": "韩十五", "name": "同桌"},  # 自定义
    ],

    # ── 工作单位 + 职位 ──
    "org": {"org": "华为技术有限公司", "title": "高级工程师"},

    # ── 简单字段 ──
    "nickname":       "小满",
    "note":           "最大创建测试-覆盖所有type枚举值",
    "birthday":       "1990-06-15",           # 公历生日 → dateList type=1 + bDay
    "birthday_lunar": "1990-05-23",           # 农历生日 → dateList type=2，服务端自动填充 bDayLunar

    # ── 头像：支持 4 种格式，自动上传+裁切为 162×162 正方形 ──
    # "avatar.jpg"                        — 本地文件路径
    # {"file": "avatar.jpg"}              — 显式指定文件路径
    # {"base64": "iVBORw0KGgo..."}        — 直接传入 Base64，仅裁切不上传
    # "iVBORw0KGgo..."                    — Base64 字符串（兼容旧用法）
    "photo": "avatar.jpg",

    # ── 群组：创建时直接加入（仅电脑端可见，手机端不显示） ──
    "groups": [
        {"group_id": "Fud_iCMH...", "group_name": "校友"},
        {"group_id": "Xk9_pQRT...", "group_name": "同事"},
    ],
})
print("最大创建:", "ok" if result.get("ok") else result.get("error"))
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `info` | `Dict[str, Any]` | 是 | 简化联系人信息字典 |
| `group_obj` | `List[Dict]` | 否 | 手动提供完整 groupObj（高级用法，覆盖 groups 自动构建） |

---

### 2.3 更新联系人 `update_contact()`

更新联系人时 **必须包含 `contact_id`**，其余字段同 `create_contact`。

```python
# 修改姓名
result = client.contacts.update_contact({
    "contact_id": "FsuGCA_OIZMv7kAS8BI9Pqbv9m70QiG3L",
    "name": "新名字",
})

# 修改电话和备注
result = client.contacts.update_contact({
    "contact_id": "FsuGCA_OIZMv7kAS8BI9Pqbv9m70QiG3L",
    "phone": "13900139999",
    "note": "新备注",
})

# 更新头像（格式同 create_contact，详见 2.2 头像注释）
result = client.contacts.update_contact({
    "contact_id": "FsuGCA_OIZMv7kAS8BI9Pqbv9m70QiG3L",
    "photo": "avatar.jpg",
})
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `info` | `Dict[str, Any]` | 是 | 简化联系人信息字典，必须含 `contact_id` |
| `group_obj` | `List[Dict]` | 否 | 手动提供完整 groupObj |

### 2.4 上传头像图片 `preview_img()`

上传联系人头像图片，获取 `photoUrl`。通常无需手动调用——`create_contact` / `update_contact` 的 `photo` 字段会自动调用此方法。

```python
# 方式1: 传入本地文件路径
result = client.contacts.preview_img("avatar.jpg")
if result.get("ok"):
    photo_url = result["photoUrl"]

# 方式2: 传入 Base64 字符串（跳过服务端上传，仅做裁切）
result = client.contacts.preview_img(base64_str, is_base64=True)
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `image` | `str` | — | 本地图片文件路径 或 Base64 编码的图片字符串 |
| `filename` | `str` | `""` | 文件名（为空则使用原文件名，仅文件路径模式有效） |
| `crop_square` | `bool` | `True` | 是否自动将图片居中裁切为正方形 |
| `square_size` | `int` | `162` | 正方形头像的像素尺寸 |
| `is_base64` | `bool` | `False` | 为 True 时 image 参数视为 Base64 字符串，跳过服务端上传 |

> 非正方形图片会自动居中裁切为 `square_size×square_size` 正方形。已是目标尺寸的图片会跳过裁切。

---

## 三、联系人删除与恢复

联系人删除采用两步机制：先移入回收站，再从回收站永久删除或恢复。

### 3.1 删除联系人（移入回收站） `delete_contacts()`

```python
result = client.contacts.delete_contacts([
    {
        "contactId": "FsuGCA_OIZMv7kAS8BI9Pqbv9m70QiG3L",
        "contactUuId": "uuid-xxx",
        "groupIdList": ["Fud_iCMH..."],
        "groupNameList": ["校友"],
    }
])
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `delete_contact_obj` | `List[Dict]` | 是 | 待删除联系人对象列表，每项含 contactId、contactUuId、groupIdList、groupNameList |

> 可从 `get_contacts()` 或 `get_design_contact()` 返回结果中获取这些字段。

---

### 3.2 恢复回收站联系人 `resume_contacts()`

从回收站恢复已删除的联系人。

```python
result = client.contacts.resume_contacts([
    "FsuGCA_OIZMv7kAS8BI9Pqbv9m70QiG3L",
    "另一个contactId",
])
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `contact_id_list` | `List[str]` | 是 | 要恢复的联系人ID列表 |

---

### 3.3 永久删除回收站联系人 `delete_recyle_contacts()`

永久删除回收站中的联系人，**不可恢复**。

```python
result = client.contacts.delete_recyle_contacts([
    "FsuGCA_OIZMv7kAS8BI9Pqbv9m70QiG3L",
])
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `contact_ids` | `List[str]` | 是 | 要永久删除的联系人ID列表 |

---

### 删除流程总结

```
正常联系人
    │
    ▼  delete_contacts()
回收站联系人
    │
    ├──▶ resume_contacts()  ──▶  恢复为正常联系人
    │
    └──▶ delete_recyle_contacts() ──▶ 永久删除（不可恢复）
```

---

## 四、群组管理

### 4.1 获取所有群组 `get_all_groups()`

```python
result = client.contacts.get_all_groups()

```

---

### 4.2 创建群组 `create_group()`

```python
result = client.contacts.create_group("校友")

if result.get("ok"):
    group_id = result.get("data", {}).get("groupId", "")
    print(f"群组创建成功，ID: {group_id}")
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `group_name` | `str` | 是 | 群组名称 |

---

### 4.3 添加联系人到群组 `add_contacts_to_groups()`

将已有的联系人添加到指定群组。

```python
result = client.contacts.add_contacts_to_groups(
    group_ids=["Fud_iCMH..."],            # 目标群组ID列表
    contact_ids=[                          # 联系人列表
        {"contactId": "FsuGCA_...", "uId": "uuid-xxx"},
        {"contactId": "AnotherId...", "uId": "uuid-yyy"},
    ],
)
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `group_ids` | `List[str]` | 是 | 目标群组ID列表 |
| `contact_ids` | `List[Dict]` | 是 | 联系人列表，每项含 `contactId` 和 `uId` |
| `group_obj` | `Dict` | 否 | 群组对象（含 groupId、groupName、contactIdList、contactUuIdList） |

> 也可以在 `create_contact` / `update_contact` 时通过 `groups` 参数直接加入群组，更简便。

### 4.4 查询联系人和群组数量 `query_count()`

返回联系人和群组的数量统计。

```python
result = client.contacts.query_count()

if result.get("ok"):
    data = result.get("data", {})
    print(f"联系人数: {data.get('contactCount', 0)}")
    print(f"群组数: {data.get('groupCount', 0)}")
```

---

## 五、导入与导出

### 5.1 导出联系人 `export_contacts()`

导出为 vCard (.vcf) 格式。

```python
# 导出并保存到文件
result = client.contacts.export_contacts(save_path="contacts.vcf")
if result.get("ok"):
    print(f"导出成功，大小: {result['size']} 字节，保存至: {result['save_path']}")

# 仅获取内容不保存
result = client.contacts.export_contacts()
if result.get("ok"):
    vcf_content = result["vcf_content"]  # bytes 类型
    print(f"导出内容大小: {len(vcf_content)} 字节")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `save_path` | `str` | `""` | 保存文件路径，为空则仅返回内容不保存 |

---

### 5.2 导入联系人 `import_contacts()`

从 VCF 文件导入联系人。`vcf_data` 支持直接传文件路径或字节内容。

```python
# 方式1: 直接传文件路径（推荐）
result = client.contacts.import_contacts(
    "contacts.vcf",
    group_name="校友",  # 可选，导入到指定群组
)

# 方式2: 传入字节内容
with open("contacts.vcf", "rb") as f:
    vcf_data = f.read()

result = client.contacts.import_contacts(
    vcf_data,
    filename="contacts.vcf",        # 字节内容模式需指定文件名
    group_name="校友",              # 可选，导入到指定群组
)

if result.get("ok"):
    print("导入成功")
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `vcf_data` | `str \| bytes` | — | VCF 文件路径（str）或字节内容（bytes） |
| `filename` | `str` | `""` | 文件名（为空则使用原文件名，仅字节内容模式有效） |
| `contact_list_id` | `str` | `""` | 联系人列表ID |
| `group_name` | `str` | `""` | 导入到的群组名称 |

---

## 六、字段类型枚举

联系人各列表字段的 `type` 值对应含义：

### 电话类型 `telList[].type`

| type | 含义 |
|------|------|
| 1 | 手机（默认） |
| 2 | 住宅 |
| 3 | 单位 |
| 14 | 总机 |
| 5 | 单位传真 |
| 6 | 住宅传真 |
| 7 | 寻呼机 |
| 8 | 其它 |
| 0 | 自定义（需填写 name） |

### 邮箱类型 `emailList[].type`

| type | 含义 |
|------|------|
| 1 | 私人（默认） |
| 2 | 单位 |
| 3 | 其它 |
| 0 | 自定义（需填写 name） |

### 即时通讯类型 `msgList[].type`

| type | 含义 |
|------|------|
| 1 | AIM（默认） |
| 2 | Windows Live |
| 3 | 雅虎 |
| 4 | Skype |
| 5 | QQ |
| 6 | 环聊 |
| 7 | ICQ |
| 8 | Jabber |
| 0 | 自定义（需填写 name） |

### 地址类型 `addressList[].type`

| type | 含义 |
|------|------|
| 1 | 住宅（默认） |
| 2 | 单位 |
| 3 | 其它 |
| 0 | 自定义（需填写 name） |

### 日期类型 `dateList[].type`

| type | 含义 | 说明 |
|------|------|------|
| 1 | 公历生日 | 通过 `birthday` 字段自动设置，同时填充 `bDay` |
| 2 | 农历生日 | 通过 `birthday_lunar` 字段自动设置，服务端自动填充 `bDayLunar`。值格式与公历相同（如 `"2003-08-23"`），手机端自动转换为公历显示 |
| 3 | 周年纪念 | `date` 字段的默认 type |
| 4 | 其它重要日期 | |

### 关系类型 `relationList[].type`

| type | 含义 |
|------|------|
| 1 | 助理 |
| 2 | 弟兄 |
| 3 | 子女 |
| 4 | 合作伙伴 |
| 5 | 父亲 |
| 6 | 朋友 |
| 7 | 上司 |
| 8 | 母亲 |
| 9 | 父母 |
| 10 | 伴侣 |
| 11 | 介绍人 |
| 12 | 亲属 |
| 13 | 姐妹 |
| 14 | 配偶 |
| 0 | 自定义（需填写 name） |

### 事件类型 `eventList[].type`

| type | 含义 |
|------|------|
| 1 | 事件（默认） |

### 使用自定义类型

简化字段默认使用 type=1，如需自定义类型，直接传完整对象：

```python
client.contacts.create_contact({
    "name": "张三",
    "phone": [
        {"type": 1, "value": "13800138000", "name": ""},   # 手机
        {"type": 3, "value": "010-12345678", "name": ""},  # 单位
    ],
    "email": [
        {"type": 2, "value": "zhangsan@work.com", "name": ""},  # 单位邮箱
    ],
    "relation": [
        {"type": 14, "value": "李四", "name": ""},  # 配偶
    ],
})
```

---

## 七、完整示例

### 7.1 查询 → 修改 → 保存

```python
# 1. 查询联系人
result = client.contacts.query_contacts_by_page()
if not result.get("ok"):
    print("查询失败")
    exit()

contacts = result.get("data", {}).get("contactList", [])
if not contacts:
    print("没有联系人")
    exit()

# 2. 获取第一个联系人的详情
first = contacts[0]
detail = client.contacts.get_design_contact([first["contactId"]])

# 3. 更新联系人
result = client.contacts.update_contact({
    "contact_id": first["contactId"],
    "name": "新名字",
    "phone": "13800138888",
})

if result.get("ok"):
    print("更新成功")
```

### 7.2 导出 → 修改 → 重新导入

```python
# 1. 导出联系人
result = client.contacts.export_contacts(save_path="backup.vcf")
if not result.get("ok"):
    print("导出失败")
    exit()

# 2. 读取并修改 VCF（按需修改）
# ... 省略修改逻辑 ...

# 3. 重新导入（直接传文件路径）
result = client.contacts.import_contacts(
    "backup.vcf",
    group_name="恢复的联系人",
)
```

### 7.3 删除 → 恢复 → 永久删除

```python
# 1. 删除联系人（移入回收站）
result = client.contacts.delete_contacts([{
    "contactId": "FsuGCA_...",
    "contactUuId": "uuid-xxx",
    "groupIdList": [],
    "groupNameList": [],
}])

# 2. 查看回收站
result = client.contacts.get_contacts(soft_del="1")

# 3. 恢复联系人
result = client.contacts.resume_contacts(["FsuGCA_..."])

# 4. 或者永久删除
result = client.contacts.delete_recyle_contacts(["FsuGCA_..."])
```

---

## 八、API 速查表

| 方法 | 对应接口 | 说明 |
|------|----------|------|
| `get_contacts()` | `POST /contact/getAllContacts` | 获取全部联系人 |
| `query_contacts_by_page()` | `POST /contact/queryContactsByPage` | 分页查询联系人 |
| `get_design_contact()` | `POST /contact/getDesignContact` | 获取指定联系人详情 |
| `create_contact()` | `POST /contact/createContact` | 创建联系人 |
| `update_contact()` | `POST /contact/updateContact` | 更新联系人 |
| `delete_contacts()` | `POST /contact/deleteContacts` | 删除联系人（移入回收站） |
| `resume_contacts()` | `POST /contact/resumeContacts` | 恢复回收站联系人 |
| `delete_recyle_contacts()` | `POST /contact/deleteRecyleContacts` | 永久删除回收站联系人 |
| `get_all_groups()` | `POST /contact/getAllGroups` | 获取所有群组 |
| `create_group()` | `POST /contact/createGroup` | 创建群组 |
| `add_contacts_to_groups()` | `POST /contact/addContacts2Groups` | 添加联系人到群组 |
| `query_count()` | `POST /contact/queryCount` | 查询联系人和群组数量 |
| `export_contacts()` | `GET /contact/exportContacts` | 导出联系人 |
| `import_contacts()` | `POST /contact/importContacts` | 导入联系人 |
| `preview_img()` | `POST /contact/previewImg` | 上传头像图片 |
