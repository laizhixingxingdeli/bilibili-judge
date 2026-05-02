# B站风纪委员 自动投票脚本

自动完成B站风纪委员的日常投票任务，支持多人多账号、多种投票策略、多渠道消息推送。

## 环境要求

- Python 3.7+
- 一个B站账号（具备风纪委员资格）

## 安装

```bash
# 1. 下载项目
git clone <仓库地址>
cd bilibili-judge

# 2. 安装依赖
pip install -r requirements.txt
```

## 首次配置（两种部署方式通用）

```bash
python judgement.py
```

首次运行会自动进入**配置向导**，共三步：

---

**第一步：B站登录**

脚本会生成一个二维码图片 `qrcode_login.png`，用 B站 APP 的扫一扫功能扫描即可登录。
二维码文件在项目目录下，直接双击打开扫码。

登录成功后，Cookies 会自动保存，有效期约 **180 天**。

---

**第二步：邮件通知（可选）**

| 配置项 | 说明 |
|--------|------|
| 发件人邮箱 | QQ邮箱地址 |
| SMTP授权码 | QQ邮箱 → 设置 → 账户 → 开启SMTP服务 → 获取授权码 |
| 收件人邮箱 | 接收通知的邮箱 |
开启 QQ邮箱 SMTP 服务教程（约1分钟）：
1. 登录 [QQ邮箱](https://mail.qq.com)
2. 点击顶部 **设置** → **账户**
3. 找到 **POP3/IMAP/SMTP服务**，点击 **开启**
4. 按提示发送短信验证，获取 **16位授权码**
5. 将授权码填入本脚本的配置向导中

> 官方教程：[什么是授权码，它又是如何设置？](https://service.mail.qq.com/detail/0/75)

当 Cookie 过期或脚本异常时，会发送邮件提醒。

---

**第三步：投票模式**

| 模式 | 行为 |
|------|------|
| **模式1**（推荐） | 有众议观点 → 跟最多的投；无观点 → 按默认选项投 |
| **模式2** | 有众议观点 → 跟最多的投；无观点 → 暂存，所有案件拉完后再统一投默认票 |

默认投票选项：
- `0` = 违规
- `1` = 不违规

**持续等待**：开启后，当日无新案件时会休眠 30 分钟再继续。

---

配置完成后，脚本会自动开始投票。

---

## 部署方式一：本地运行（Windows / Linux 桌面）

适合在自己电脑上运行。

```bash
# 配置有效时直接投票
python judgement.py

# 无案件时保持等待（开启 once=true）
# 脚本会休眠30分钟后继续
```

需要长期运行时，开一个终端挂着即可。也可以用任务计划程序（Windows）或 systemd（Linux 桌面）实现开机自启。

## 部署方式二：远程 Linux 服务器

适合部署到 VPS 上 7×24 小时运行。

### 1. 将项目传到服务器

```bash
rsync -avz --exclude 'venv' --exclude '__pycache__' bilibili-judge/ root@你的服务器IP:/opt/bilibili-judge/
```

### 2. 服务器上安装依赖

```bash
ssh root@你的服务器IP
cd /opt/bilibili-judge
pip install -r requirements.txt
```

### 3. 首次配置（扫码登录）

登录向导会在服务器上生成二维码图片，需要下载到本地扫码：

```bash
# 在服务器上运行配置向导
ssh root@你的服务器IP "cd /opt/bilibili-judge && python judgement.py"

# 另开一个终端，在本地下载二维码并扫码
scp root@你的服务器IP:/opt/bilibili-judge/qrcode_login.png ./
```

用 B站 APP 扫 `qrcode_login.png` 后，回到第一个终端，按 Enter 继续完成配置。

### 4. 配置定时任务

```bash
ssh root@你的服务器IP
crontab -e
```

添加一行（每天晚上10点跑一次）：

```
0 22 * * * cd /opt/bilibili-judge && python judgement.py >> run.log 2>&1
```

查看运行日志：

```bash
tail -f /opt/bilibili-judge/run.log
```

## 日常使用

```bash
# 直接运行（配置有效时）
python judgement.py

# 重新配置（如需要换账号）
python setup.py
```

登录有效期 180 天，到期前会提示重新扫码，运行 `python setup.py` 即可。

## 配置文件

所有配置保存在 `config/config.json`，结构如下：

```json
{
  "appkey": "B站TV端API密钥（已内置默认值）",
  "appsec": "B站TV端API密钥（已内置默认值）",
  "email": {
    "sender": "发件人邮箱",
    "password": "SMTP授权码",
    "recipient": "收件人邮箱",
    "smtp_server": "smtp.qq.com",
    "smtp_port": 587
  },
  "http_header": {
    "User-Agent": "浏览器UA",
    "Referer": "https://www.bilibili.com/",
    "Connection": "keep-alive"
  },
  "default_vote": {
    "mode": 1,
    "vote": [0, 1],
    "once": true
  },
  "users": [
    {
      "cookieDatas": {
        "SESSDATA": "登录态cookie",
        "bili_jct": "CSRF token",
        "DedeUserID": "用户ID"
      }
    }
  ],
  "push": {
    "enable": false,
    "msgtpye": ["CookieExpires", "UnknownError", "DailyMissions"],
    "wxpush": { "enable": false },
    "tgpush": { "enable": false },
    "server": { "enable": false },
    "ijingniu": { "enable": false },
    "pushplus": { "enable": false }
  }
}
```

## 推送通知

支持以下渠道（默认全部关闭，需手动在 `config.json` 中开启）：

| 渠道 | 配置位置 | 说明 |
|------|---------|------|
| 邮件 | `email` | QQ邮箱 SMTP |
| 企业微信 | `push.wxpush` | 企业微信应用消息 |
| Telegram | `push.tgpush` | Bot 推送 |
| Server酱 | `push.server` | Server酱推送 |
| 即时达 | `push.ijingniu` | 即时达推送 |
| PushPlus | `push.pushplus` | PushPlus 推送 |

推送类型：
- `CookieExpires` — Cookie 过期提醒
- `UnknownError` — 未知错误提醒
- `DailyMissions` — 每日投票统计

## 项目结构

```
bilibili-judge/
├── judgement.py       入口 — 自动检测配置 → 进入向导或直接投票
├── setup.py           配置向导 — 扫码登录 + 基础设置
├── api.py             B站 API 封装
├── voter.py           投票逻辑（模式1/模式2）
├── auth.py            登录 / Token 刷新
├── notify.py          邮件 + 多渠道推送通知
├── config.py          配置加载 + API 签名
├── requirements.txt
├── README.md
└── config/
    ├── config.json    所有配置
    └── info.json      登录凭据（自动生成）
```

## 免责声明

- 本脚本仅用于学习和测试目的
- 请勿用于商业用途
- 使用本脚本产生的任何后果由使用者自行承担
- 请在下载后 24 小时内删除
