# 极简折线图生成服务

只做一件事：**接收月报数据 → 生成 4 张折线图 → 返回 base64**。不发信、不连 SMTP。

## 运行（在那台能装库的服务器上）

```bash
pip install pillow
python chart_server.py          # 默认 0.0.0.0:8790；改端口：PORT=8791 python chart_server.py
```

## 验证

```bash
curl -X POST http://127.0.0.1:8790/make_charts \
     -H "Content-Type: application/json" \
     -d '{"period":"测试","computer":{}}'
```

返回：`{"status":"ok","report":{...},"charts":{"chart_cpu":"<base64>"...}}`

## Dify 工作流接线

```
[数据节点 reportjson]
  → [HTTP 请求节点] POST http://<服务器IP>:8790/make_charts，请求体 = reportjson
  → [发送月报插件工具（v0.0.17）] data = HTTP 节点返回的整个 JSON
```

插件自动：剥标签 → 解析 report + charts → 渲染 HTML → 图片 cid 内嵌 → SMTP 发送。

## 文件

- `chart_server.py` 主程序（只含 /make_charts）
- `charts.py` 画图（Pillow + SimHei）
- `_assets/simhei.ttf` 中文字体
