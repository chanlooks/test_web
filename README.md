# 月报邮件系统 · 部署指南 (v0.0.18)

两套组件配合使用：

| 组件 | 文件 | 装在哪 |
|------|------|--------|
| **邮件插件** | `langgenius-email_0.0.18.difypkg` | Dify 平台 |
| **图表服务** | `standalone_server/` | 一台能装 Pillow 的服务器 |

---

## 一、部署图表服务

在一台 **能 pip 装库** 的 Linux/Windows 服务器上：

```bash
# 1. 上传 standalone_server/ 整个目录到服务器
scp -r standalone_server/ user@server:/opt/chart-server/

# 2. 安装依赖
cd /opt/chart-server
pip install pillow

# 3. 设置 AK（可选，强烈建议生产环境开启）
export CHART_API_KEY="your-random-secret-key"

# 4. 启动（默认 8790 端口）
python chart_server.py

# 或指定端口
PORT=8888 python chart_server.py
```

验证：
```bash
# 无 AK 时：
curl -X POST http://127.0.0.1:8790/make_charts \
     -H "Content-Type: application/json" \
     -d '{"period":"测试","computer":{}}'

# 有 AK 时：
curl -X POST http://127.0.0.1:8790/make_charts \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer your-random-secret-key" \
     -d '{"period":"测试","computer":{}}'

# 正常返回：{"status":"ok","report":{...},"charts":{"chart_cpu":"<base64>"...}}
```

> 建议用 systemd 或 supervisor 做成常驻服务。

---

## 二、安装插件

### 2.1 上传插件包

Dify → 插件 → 本地插件包 → 上传 `langgenius-email_0.0.18.difypkg`

> 如果提示签名校验失败：Dify 设置里生成插件私钥，用 `dify-plugin plugin package` 重新签名。

### 2.2 配置 SMTP

在插件设置里填：

| 参数 | 说明 |
|------|------|
| `smtp_server` | SMTP 服务器地址 |
| `smtp_port` | 端口（SSL: 465, TLS: 587） |
| `encrypt_method` | SSL / TLS / NONE |
| `email_account` | 发件邮箱账号 |
| `email_password` | 发件邮箱密码 |
| `sender_address` | 发件人地址（可和账号相同） |

> 如果走内网免认证 SMTP 中继，账号密码留空，只填 `sender_address`。

---

## 三、Dify 工作流接线

打开现有的"基础设施服务月报助手"工作流，**删除"模板转换"节点**，在"条件分支"的 `true` 出口后面接 2 个新节点：

### 节点 1：HTTP 请求（调图表服务）

| 字段 | 值 |
|------|-----|
| 方法 | `POST` |
| URL | `http://<图表服务器IP>:8790/make_charts` |
| Headers | `Authorization: Bearer <CHART_API_KEY>`（如已配置） |
| 请求体 | JSON → 选 **LLM 节点** 的 `text` 输出 |

### 节点 2：发送月报（含折线图）

| 参数 | 绑定 |
|------|------|
| `data` | HTTP 节点的 `body` 输出 |
| `send_to` | 收件人邮箱（如 `leader@company.com`） |
| `subject` | 邮件主题（如 `IT 基础设施资源月报 - 2026年8月`） |

### 最终接线图

```
开始 → 获取当前时间 → 7个API并行 → LLM → 代码校验 → 条件分支
                                                       ├─ true → HTTP请求(mark_charts) → 发送月报 → 结束
                                                       └─ false → 结束
```

> **简化方案**：如果 Dify 服务器能 `pip install pillow`，可以跳过 HTTP 节点。直接把 LLM 的 `text` 输出接到"发送月报"工具的 `data` 参数，插件内置的 Pillow 会自动画图。

---

## 四、验证

1. 先发给自己，用 Outlook 打开：图表正常显示、无破图、布局 OK
2. 确认无误后再发给领导

---

## 五、更新插件（源码修改后重新打包）

如果改了 `plugin_official_src/` 下的源码，需要重新打包：

```bash
# 方式一：用 Python 直接打包
python -c "
import zipfile, os
src = 'plugin_official_src'
with zipfile.ZipFile('langgenius-email_0.0.18.difypkg', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f in ('.verification.dify.json', 'uv.lock'):
                continue
            path = os.path.join(root, f)
            z.write(path, os.path.relpath(path, src))
"

# 方式二：用 dify-plugin CLI（需安装 pip install dify-plugin）
dify-plugin plugin package -p plugin_official_src
```

### 核心源码文件说明

| 文件 | 作用 |
|------|------|
| `tools/charts.py` | Pillow 图表生成（折线图 + 条形图） |
| `tools/report_render.py` | 邮件 HTML 渲染器（960px 宽度、Outlook 兼容） |
| `tools/send_monthly_report.py` | 发送月报工具入口 |
| `tools/send.py` | SMTP 发送核心（支持 cid 内嵌图片） |

图表服务的 `standalone_server/charts.py` 和插件保持一致，改完记得同步替换。

---

## 常见问题

**Q: 图表显示破图？**
- 确认 HTTP 节点的输出正确接到了"发送月报"工具的 `data` 参数
- 确认图表服务器正常返回了 `charts` 字段

**Q: 图表服务返回 401？**
- 确认 Dify HTTP 节点加了 `Authorization` Header
- 确认 key 和服务器 `CHART_API_KEY` 一致

**Q: 插件装不上 / 签名报错？**
- Dify 设置 → 生成插件私钥 → `dify-plugin plugin package -p plugin_official_src -k key.pem`
- 用签名后的包重新上传

**Q: 邮件里图表大小/颜色不对？**
- 改 `tools/charts.py` → 重新打包插件 + 同步 `standalone_server/charts.py`
- 改 `tools/report_render.py` → 重新打包插件

**Q: 只想改邮件宽度/卡片样式？**
- 改 `tools/report_render.py` 里的 `width` 值，重新打包插件即可，不需要动图表服务
