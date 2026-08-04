# 月报邮件系统 · 最终使用指南

两套东西配合使用，缺一不可：

| 交付物 | 作用 | 装在哪 |
|--------|------|--------|
| **`langgenius-email_0.0.17.difypkg`**（插件） | 接收数据+图片 → 渲染 HTML → 内嵌图片 → SMTP 发送 | **Dify**（离线也能装，无 Pillow 依赖） |
| **`report-chart-server-minimal.zip`**（图表服务） | 接收数据 → 用 Pillow 画 8 张图 → 返回 base64 | **那台能装库的生产服务器** |

---

## 一、部署图表服务（生产服务器）

```bash
# 1. 解压
unzip report-chart-server-minimal.zip
cd standalone_server

# 2. 装依赖（这台能装）
pip install pillow

# 3. 启动（默认 0.0.0.0:8790）
python chart_server.py
```

验证：
```bash
curl -X POST http://127.0.0.1:8790/make_charts \
     -H "Content-Type: application/json" \
     -d '{"period":"测试","computer":{}}'
# 返回 {"status":"ok","report":{...},"charts":{"chart_cpu":"<base64>"...}}
```

## 二、装插件 + 配 SMTP（Dify）

1. Dify → 插件 → 本地插件包 → 上传 `langgenius-email_0.0.17.difypkg`
   - 若提示签名校验失败：按下方「签名」处理
2. 插件设置里配 SMTP：`smtp_server` / `smtp_port` / `encrypt_method` / **`email_account`（账号）** / **`email_password`（密码）** / `sender_address`
   - 账号密码必填（官方原版行为）

## 三、Dify 工作流接线（3 个节点）

```
[数据节点 reportjson]
   ↓
[HTTP 请求节点]
   URL:  http://<服务器IP>:8790/make_charts
   方法: POST
   请求体: reportjson
   ↓  得到 {"report":..., "charts":{cid: base64}}
[发送月报（含折线图）工具]
   data    = HTTP 节点返回的整个 JSON
   send_to = 领导邮箱
   subject = 邮件主题
   → 插件解码图片 → 渲染 HTML → cid 内嵌 → SMTP 发送
```

- `data` 带不带 `<REPORT_JSON>` 标签都能解析
- 不再需要原来的模板转换节点（邮件版 HTML 由插件自己生成）

## 四、先自测再发领导

1. 先发给自己，用 Outlook 打开确认：图表正常显示、无破图、布局 OK
2. 确认后再发给领导

---

## 常见问题

**Q: 插件装不上 / 报错？**
- 签名校验失败 → Dify 设置里生成插件私钥，用 `dify-plugin plugin package -p <源码目录> -k key.pem` 重签再传
- 其它报错 → 把报错发我

**Q: 图表服务起不来？**
- 确认 `pip install pillow` 成功
- 确认端口 8790 没被占用、Dify 能访问该服务器（网络互通）

**Q: 图表显示破图？**
- 说明 `data` 没接 HTTP 节点输出，或服务器没返回对应 cid 的图。检查 HTTP 节点输出和工具的 data 绑定。

**Q: 想改图表/邮件样式？**
- HTML 样式 → `plugin_official_src/tools/report_render.py`，改完重新打包插件
- 折线图/条形图样式 → `standalone_server/charts.py`，改完拷到服务器替换 + 重启
- ⚠️ 别改图表的 cid 名（`chart_cpu` 等），HTML 引用按这个名字找图
