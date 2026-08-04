import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from typing import List, Optional, Dict, Tuple

from pydantic import BaseModel
from dify_plugin.file.file import File


class SendEmailToolParameters(BaseModel):
    smtp_server: str
    smtp_port: int

    email_account: Optional[str] = None
    email_password: Optional[str] = None
    sender_address: str

    sender_to: List[str]
    subject: str
    email_content: str
    encrypt_method: str

    is_html: bool = False
    is_raw_html: bool = False
    plain_text_content: Optional[str] = None
    attachments: Optional[List[File]] = None
    # (content_id, data_bytes, mime_subtype) —— HTML 里用 <img src="cid:content_id">
    inline_images: Optional[List[Tuple[str, bytes, str]]] = None

    cc_recipients: List[str] = []

    reply_to_address: Optional[str] = None


def _build_message(params: SendEmailToolParameters) -> MIMEMultipart:
    """构造 MIME 邮件。有内嵌图片时用 multipart/related 保证 cid 引用可用。"""
    msg = MIMEMultipart("mixed")

    msg["From"] = params.sender_address
    if params.reply_to_address:
        msg.add_header("Reply-To", params.reply_to_address)
    msg["To"] = ", ".join(params.sender_to)
    if params.cc_recipients:
        msg["CC"] = ", ".join(params.cc_recipients)
    msg["Subject"] = params.subject

    # ---- 正文：纯文本 + HTML ----
    if params.is_raw_html:
        import re
        plain_text = re.sub(r'<[^>]+>', '', params.email_content)
        html_part = MIMEText(params.email_content, "html")
    else:
        plain_text = params.plain_text_content if params.is_html and params.plain_text_content else params.email_content
        html_part = MIMEText(params.email_content, "html") if params.is_html else None

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(plain_text, "plain"))
    if html_part is not None:
        alt_part.attach(html_part)

    # ---- 内嵌图片（cid）或普通正文 ----
    if params.inline_images:
        related = MIMEMultipart("related")
        related.attach(alt_part)
        for cid, data, subtype in params.inline_images:
            try:
                part = MIMEImage(data, _subtype=subtype or "octet-stream")
            except Exception:
                part = MIMEApplication(data)
            part.add_header("Content-ID", "<%s>" % cid)
            part.add_header("Content-Disposition", "inline",
                            filename="%s.%s" % (cid, subtype or "png"))
            related.attach(part)
        msg.attach(related)
    else:
        msg.attach(alt_part)

    # ---- 普通附件 ----
    if params.attachments:
        for attachment in params.attachments:
            file_data = attachment.blob
            filename = getattr(attachment, 'filename', 'attachment')
            part = MIMEApplication(file_data)
            part.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(part)

    return msg


def send_mail(params: SendEmailToolParameters) -> Dict[str, Tuple[int, bytes]]:
    timeout = 60

    msg = _build_message(params)

    # Combine all recipients for sending
    all_recipients = params.sender_to + params.cc_recipients + params.bcc_recipients

    ctx = ssl.create_default_context()
    try:
        if params.encrypt_method.upper() == "SSL":
            with smtplib.SMTP_SSL(params.smtp_server, params.smtp_port, context=ctx, timeout=timeout) as server:
                server.login(params.email_account, params.email_password)
                return server.sendmail(params.sender_address, all_recipients, msg.as_string())
        else:  # NONE or TLS
            with smtplib.SMTP(params.smtp_server, params.smtp_port, timeout=timeout) as server:
                if params.encrypt_method.upper() == "TLS":
                    server.starttls(context=ctx)
                server.login(params.email_account, params.email_password)
                return server.sendmail(params.sender_address, all_recipients, msg.as_string())
    except Exception as e:
        logging.exception(f"Send email failed: {str(e)}")
        # Return an empty dictionary to match the expected return type
        return {}
