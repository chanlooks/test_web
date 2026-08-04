import base64
import json
import re
from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.report_render import render
from tools.send import SendEmailToolParameters, send_mail

# 注意：tools.charts 需要 Pillow，这里改为按需惰性导入。
# - 外部提供 base64 图表时（data 含 charts 字段），全程不需要 Pillow，离线 Dify 可用。
# - 没有外部图表时才尝试内置 Pillow 画图（需生产区能装 Pillow）。


class SendMonthlyReportTool(Tool):
    """发送月报邮件。

    data 参数两种形态：
      1) 直接是月报数据 JSON（内置 Pillow 画图路径）
      2) {"report": <月报数据>, "charts": {"chart_cpu": "<base64 PNG>", ...}}（外部生成图片路径，无需 Pillow）
    """

    def _parse_email_list(self, raw, rgx, field):
        if not raw:
            return []
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format for {field} list")
        if not isinstance(items, list):
            raise ValueError(f"{field} must be a JSON list")
        for item in items:
            if not isinstance(item, str) or not rgx.match(item):
                raise ValueError(f"Invalid {field} email: {item}")
        return items

    def _resolve_charts(self, data):
        """返回 (report, charts)。charts = [(cid, png_bytes, 'png'), ...]"""
        if isinstance(data, dict) and isinstance(data.get("charts"), dict):
            # ---- 外部图片路径：不依赖 Pillow ----
            report = data.get("report", data)
            charts = []
            for cid, b64 in data["charts"].items():
                try:
                    charts.append((str(cid), base64.b64decode(b64), "png"))
                except Exception:
                    continue
            if not charts:
                raise ValueError("no valid base64 charts in data.charts")
            return report, charts
        # ---- 内置 Pillow 画图路径 ----
        try:
            from tools.charts import build_charts
        except Exception as e:
            raise RuntimeError(
                f"Pillow/charts unavailable: {e}. "
                f"请在另一台能装库的服务器生成折线图，并通过 data.charts 传 base64 图片。"
            )
        try:
            return data, build_charts(data)
        except Exception as e:
            raise RuntimeError(f"Chart generation failed: {e}")

    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        sender = self.runtime.credentials.get("email_account", "")
        email_rgx = re.compile(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$")
        password = self.runtime.credentials.get("email_password", "")

        smtp_server = self.runtime.credentials.get("smtp_server", "")
        if not smtp_server:
            yield self.create_text_message("please input smtp server")
            return
        try:
            smtp_port = int(self.runtime.credentials.get("smtp_port", ""))
        except ValueError:
            yield self.create_text_message("Invalid parameter smtp_port(should be int)")
            return

        sender_address = self.runtime.credentials.get("sender_address", "") or sender
        if not sender_address:
            yield self.create_text_message(
                "Sender Address is required when Email Account is not provided. "
                "Please set the 'Sender Address' field in credentials."
            )
            return
        if not email_rgx.match(sender_address):
            yield self.create_text_message(
                f"Invalid sender address '{sender_address}'. The sender address must be a valid email format."
            )
            return

        encrypt_method = self.runtime.credentials.get("encrypt_method", "")
        if not encrypt_method:
            yield self.create_text_message("please input encrypt method")
            return

        receiver_email = tool_parameters.get("send_to", "")
        if not receiver_email:
            yield self.create_text_message("please input receiver email")
            return
        if not email_rgx.match(receiver_email):
            yield self.create_text_message(
                f"Invalid parameter receiver email, the receiver email({receiver_email}) is not a mailbox"
            )
            return

        subject = tool_parameters.get("subject", "")
        if not subject:
            yield self.create_text_message("please input subject")
            return

        data_raw = tool_parameters.get("data", "")
        if not data_raw:
            yield self.create_text_message("please input report data (JSON)")
            return
        # data 可能是 JSON 字符串（带 <REPORT_JSON> 标签或纯 JSON），也可能是 Dify 传来的 dict
        if isinstance(data_raw, str):
            data_raw = data_raw.replace('<REPORT_JSON>', '').replace('</REPORT_JSON>', '').strip()
            try:
                data = json.loads(data_raw)
            except json.JSONDecodeError:
                yield self.create_text_message("Invalid JSON format for report data")
                return
        else:
            data = data_raw

        try:
            cc_list = self._parse_email_list(tool_parameters.get("cc", ""), email_rgx, "cc")
            bcc_list = self._parse_email_list(tool_parameters.get("bcc", ""), email_rgx, "bcc")
        except ValueError as e:
            yield self.create_text_message(str(e))
            return

        reply_to = tool_parameters.get("reply_to", None) or None

        # 1) 解析图表来源（外部 base64 或内置 Pillow）
        try:
            report, charts = self._resolve_charts(data)
        except Exception as e:
            yield self.create_text_message(str(e))
            return

        # 2) 渲染静态 HTML（趋势段引用 cid 图片）
        try:
            html = render(report)
        except Exception as e:
            yield self.create_text_message(f"HTML render failed: {e}")
            return

        params = SendEmailToolParameters(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            email_account=sender,
            email_password=password,
            sender_address=sender_address,
            sender_to=[receiver_email],
            subject=subject,
            email_content=html,
            encrypt_method=encrypt_method,
            is_html=True,
            is_raw_html=True,
            inline_images=charts,
            cc_recipients=cc_list,
            bcc_recipients=bcc_list,
            reply_to_address=reply_to,
        )

        result = send_mail(params)
        if result:
            error_messages = []
            for key, (integer_value, bytes_value) in result.items():
                error_messages.append(f"{key}: {integer_value} {bytes_value.decode('utf-8')}")
            yield self.create_text_message(f"Email sending failed: {', '.join(error_messages)}")
        else:
            msg = f"Email sent successfully to {receiver_email}"
            if charts:
                msg += f" with {len(charts)} inline chart(s)"
            if cc_list:
                msg += f", CC: {', '.join(cc_list)}"
            if bcc_list:
                msg += f", BCC: {', '.join(bcc_list)}"
            yield self.create_text_message(msg)
