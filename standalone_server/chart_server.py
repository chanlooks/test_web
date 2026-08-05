# -*- coding: utf-8 -*-
"""
折线图生成服务（供 Dify 离线场景使用）

作用：接收 Dify HTTP 节点 POST 过来的月报数据，
      用 Pillow 生成折线图/条形图 PNG，转 base64 返回给 Dify 插件发送邮件。
      本服务只画图，不发信、不连 SMTP。

依赖：仅 Pillow（charts.py 用）+ 标准库。
运行：
    pip install pillow
    python chart_server.py          # 默认 0.0.0.0:8790

可选认证（生产环境建议开启）：
    export CHART_API_KEY="your-secret-key"
    客户端请求时带 Header: Authorization: Bearer your-secret-key

Dify 工作流接线：
    [数据节点 reportjson] → [HTTP 请求节点]
      URL:    http://<本服务器IP>:8790/make_charts
      方法:   POST
      Header: Authorization: Bearer <CHART_API_KEY>  (如已配置)
      请求体: 月报数据 JSON（带不带 <REPORT_JSON> 标签都行，会自动剥）
      返回:   {"status":"ok", "report": <数据>, "charts": {"chart_cpu": "<base64 PNG>", ...}}
    然后把返回的整个 JSON 作为「发送月报」插件工具的 data 参数即可。
"""
import base64
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import charts

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8790))
API_KEY = os.environ.get("CHART_API_KEY", "")  # 空字符串 = 不校验


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _check_auth(self):
        """验证 API Key。未配置 key 时跳过。"""
        if not API_KEY:
            return True
        # 支持 Authorization: Bearer <key> 或 X-API-Key: <key>
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:] == API_KEY
        x_api_key = self.headers.get("X-API-Key", "")
        if x_api_key:
            return x_api_key == API_KEY
        return False

    def do_POST(self):
        if self.path != "/make_charts":
            self._reply(404, {"status": "error", "message": "not found"})
            return

        if not self._check_auth():
            self._reply(401, {"status": "error", "message": "unauthorized: invalid or missing API key"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            self._reply(400, {"status": "error", "message": "bad json body: %s" % e})
            return

        data = body.get("data", body)  # 兼容直接把数据作为 body
        if isinstance(data, str):
            data = data.replace("<REPORT_JSON>", "").replace("</REPORT_JSON>", "").strip()
            try:
                data = json.loads(data)
            except Exception as e:
                self._reply(400, {"status": "error", "message": "bad report data: %s" % e})
                return

        try:
            chart_list = charts.build_charts(data)
        except Exception as e:
            self._reply(500, {"status": "error", "message": "chart generation failed: %s" % e})
            return

        b64 = {cid: base64.b64encode(png).decode("ascii") for cid, png, _ in chart_list}
        self._reply(200, {"status": "ok", "report": data, "charts": b64})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if API_KEY:
        print("图表服务已启动: %s:%s  (POST /make_charts)  [AK 已启用]" % (HOST, PORT))
    else:
        print("图表服务已启动: %s:%s  (POST /make_charts)  [无 AK 认证]" % (HOST, PORT))
    HTTPServer((HOST, PORT), Handler).serve_forever()
