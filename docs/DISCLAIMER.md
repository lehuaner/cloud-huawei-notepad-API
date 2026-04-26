# 免责声明 / Disclaimer

> **[English version below](#english-version)**

---

## 中文版

### ⚠️ 重要提示

**本项目仅供学习、研究和技术交流使用，严禁用于任何商业或非法用途。**

### 1. 项目性质

本项目（Cloud Space API）是一个基于逆向工程技术分析的非官方 Python SDK，**与华为技术有限公司（Huawei Technologies Co., Ltd.）没有任何关联、授权或认可**。本项目不隶属于华为公司，也不代表华为公司的立场。

本项目通过分析华为云空间（cloud.huawei.com）Web 端的公开通信协议，对 API 接口进行了封装。所有接口均来自浏览器与服务器之间的正常 HTTP 通信数据。

### 2. 使用限制

使用本项目时，您必须遵守以下规则：

- **仅供学习与研究**：本项目仅用于学习逆向工程技术、HTTP 协议分析、Python SDK 设计等技术领域。
- **禁止商业使用**：严禁将本项目用于任何商业目的，包括但不限于付费服务、数据贩卖、自动化批量操作等。
- **禁止非法用途**：严禁利用本项目从事任何违反法律法规的活动，包括但不限于：
  - 未经授权访问他人账户或数据
  - 窃取、篡改、破坏他人数据
  - 进行网络攻击或干扰服务正常运行
  - 侵犯他人隐私或知识产权
- **遵守服务条款**：使用本项目可能违反华为云空间的服务条款（Terms of Service），用户需自行承担因违反服务条款而产生的一切后果。
- **合理使用**：请控制请求频率，避免对华为服务器造成过大负担。滥用可能导致账号被封禁。

### 3. 风险告知

使用本项目存在以下风险，**使用者需自行承担全部风险**：

- **账号风险**：使用非官方客户端登录可能导致账号被标记、限制或封禁
- **数据风险**：API 接口可能随时变更，导致数据丢失或损坏
- **法律风险**：逆向工程在某些司法管辖区可能受到法律限制
- **安全风险**：本项目不提供任何安全保证，可能存在未知漏洞
- **服务中断**：华为可能随时修改 API，导致本项目完全失效

### 4. 知识产权

- 本项目代码采用 MIT 许可证开源，但**不授予任何华为商标、服务标识或相关知识产权的使用权**
- "华为"、"Huawei"、"华为云空间"等名称和标识是华为技术有限公司的商标或注册商标
- 本项目中引用的 API 端点、协议格式等均为华为公司的专有技术

### 5. 免责条款

在适用法律允许的最大范围内：

1. 本项目按"原样"（AS IS）提供，**不作任何明示或暗示的保证**，包括但不限于适销性、特定用途的适用性和非侵权性
2. **作者不对使用本项目产生的任何直接、间接、偶然、特殊或后果性损害承担责任**，包括但不限于：
   - 数据丢失或损坏
   - 账号被封禁或限制
   - 利润损失或业务中断
   - 法律诉讼或行政处罚
3. 作者没有义务对本项目提供维护、更新或技术支持
4. 本项目不提供任何形式的担保，包括其对特定目的的适用性

### 6. 法律合规

- 使用者应当遵守所在地区的法律法规，包括但不限于《中华人民共和国网络安全法》、《中华人民共和国数据安全法》、《中华人民共和国个人信息保护法》等
- 逆向工程的合法性因地区而异，使用者需自行确认当地法律是否允许此类活动
- 如果华为公司提出要求，作者将配合删除或修改侵权内容

### 7. 删除请求

如果您是华为技术有限公司的代表，认为本项目侵犯了您的权益，请通过以下方式联系：

- 在 GitHub 仓库提交 Issue


仓库拥有者将在收到有效通知后及时处理。

---

## English Version

### ⚠️ Important Notice

**This project is for educational and research purposes only. Any commercial or illegal use is strictly prohibited.**

### 1. Nature of the Project

This project (Cloud Space API) is an unofficial Python SDK based on reverse engineering technical analysis. **It is not affiliated with, authorized by, or endorsed by Huawei Technologies Co., Ltd. in any way.** This project does not represent the views or positions of Huawei.

This project encapsulates API interfaces by analyzing the public communication protocols between the browser and server of Huawei Cloud Space (cloud.huawei.com). All interfaces are derived from normal HTTP communication data between browsers and servers.

### 2. Usage Restrictions

When using this project, you must comply with the following rules:

- **Educational and Research Only**: This project is intended solely for learning reverse engineering, HTTP protocol analysis, Python SDK design, and related technical fields.
- **No Commercial Use**: It is strictly prohibited to use this project for any commercial purpose, including but not limited to paid services, data sales, or automated bulk operations.
- **No Illegal Use**: It is strictly prohibited to use this project for any illegal activities, including but not limited to:
  - Unauthorized access to others' accounts or data
  - Theft, alteration, or destruction of others' data
  - Conducting cyberattacks or interfering with normal service operations
  - Violating others' privacy or intellectual property rights
- **Terms of Service Compliance**: Using this project may violate Huawei Cloud Space's Terms of Service. Users bear all consequences arising from such violations.
- **Fair Use**: Please control request frequency to avoid placing excessive load on Huawei's servers. Abuse may result in account bans.

### 3. Risk Disclosure

Using this project carries the following risks. **Users assume all risks entirely:**

- **Account Risk**: Logging in with unofficial clients may result in your account being flagged, restricted, or banned
- **Data Risk**: API interfaces may change at any time, potentially causing data loss or corruption
- **Legal Risk**: Reverse engineering may be legally restricted in certain jurisdictions
- **Security Risk**: This project provides no security guarantees and may contain unknown vulnerabilities
- **Service Disruption**: Huawei may modify APIs at any time, rendering this project completely non-functional

### 4. Intellectual Property

- This project's code is open-sourced under the MIT License, but **it does not grant any right to use Huawei trademarks, service marks, or related intellectual property**
- "Huawei", "华为", "Huawei Cloud Space" and other names and logos are trademarks or registered trademarks of Huawei Technologies Co., Ltd.
- The API endpoints and protocol formats referenced in this project are proprietary technologies of Huawei

### 5. Disclaimer of Liability

To the maximum extent permitted by applicable law:

1. This project is provided "AS IS" without warranty of any kind, **express or implied**, including but not limited to merchantability, fitness for a particular purpose, and non-infringement
2. **The author shall not be liable for any direct, indirect, incidental, special, or consequential damages arising from the use of this project**, including but not limited to:
   - Data loss or corruption
   - Account bans or restrictions
   - Loss of profits or business interruption
   - Legal proceedings or administrative penalties
3. The author has no obligation to provide maintenance, updates, or technical support for this project
4. This project provides no warranty of any kind, including its suitability for any particular purpose

### 6. Legal Compliance

- Users should comply with the laws and regulations of their jurisdiction, including but not limited to the Cybersecurity Law, Data Security Law, and Personal Information Protection Law of the People's Republic of China
- The legality of reverse engineering varies by jurisdiction; users must independently verify whether such activities are permitted under local law
- If Huawei Technologies Co., Ltd. makes a request, the author will cooperate in removing or modifying infringing content

### 7. Takedown Requests

If you are a representative of Huawei Technologies Co., Ltd. and believe this project infringes on your rights, please contact us by:

- Filing an Issue on the GitHub repository

The owner will process valid takedown requests promptly.

---

**By using this project, you acknowledge that you have read, understood, and agree to be bound by this disclaimer.**

**使用本项目即表示您已阅读、理解并同意受本免责声明约束。**
