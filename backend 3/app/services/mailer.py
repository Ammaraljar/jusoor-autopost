"""The company's sending account for newsletters.

Three ways to connect, like the usual newsletter tools:
- smtp:   the company's own mailbox or any SMTP service (Gmail/Google Workspace, Outlook/Microsoft 365,
          Zoho, Brevo SMTP, SendGrid, Mailgun, Amazon SES…), with ready presets;
- brevo:  Brevo (Sendinblue) API key — works where SMTP ports are blocked;
- resend: Resend API key — same.
Secrets are stored per company and never sent back to the browser.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..db import AppSetting
from . import app_settings

KEY = "email"
SECRETS = ("smtp_password", "brevo_api_key", "resend_api_key")
FIELDS = ("provider", "from_name", "from_email", "reply_to", "smtp_host", "smtp_port", "smtp_security", "smtp_user",
          "smtp_password", "brevo_api_key", "resend_api_key", "company_address", "batch_per_minute")
DEFAULTS: dict[str, Any] = {"provider": "brevo", "from_name": "", "from_email": "", "reply_to": "", "smtp_host": "",
                            "smtp_port": 587, "smtp_security": "starttls", "smtp_user": "", "smtp_password": "",
                            "brevo_api_key": "", "resend_api_key": "", "company_address": "", "batch_per_minute": 120}
PRESETS = {
    "gmail": {"label": "Gmail / Google Workspace", "smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_security": "starttls",
              "help": "app_password"},
    "outlook": {"label": "Outlook / Microsoft 365", "smtp_host": "smtp.office365.com", "smtp_port": 587, "smtp_security": "starttls"},
    "zoho": {"label": "Zoho Mail", "smtp_host": "smtp.zoho.com", "smtp_port": 465, "smtp_security": "ssl"},
    "brevo_smtp": {"label": "Brevo SMTP", "smtp_host": "smtp-relay.brevo.com", "smtp_port": 587, "smtp_security": "starttls"},
    "sendgrid": {"label": "SendGrid", "smtp_host": "smtp.sendgrid.net", "smtp_port": 587, "smtp_security": "starttls"},
    "mailgun": {"label": "Mailgun", "smtp_host": "smtp.mailgun.org", "smtp_port": 587, "smtp_security": "starttls"},
    "ses": {"label": "Amazon SES", "smtp_host": "email-smtp.us-east-1.amazonaws.com", "smtp_port": 587, "smtp_security": "starttls"},
    "hostinger": {"label": "Hostinger", "smtp_host": "smtp.hostinger.com", "smtp_port": 465, "smtp_security": "ssl"},
    "custom": {"label": "Custom SMTP", "smtp_host": "", "smtp_port": 587, "smtp_security": "starttls"},
}


class MailError(Exception):
    pass


def _row(db: Session) -> AppSetting | None:
    return db.get(AppSetting, app_settings.row_key(KEY))


def load(db: Session) -> dict[str, Any]:
    row = _row(db)
    return {**DEFAULTS, **((row.value or {}) if row else {})}


def public(db: Session) -> dict[str, Any]:
    cfg = load(db)
    out = {k: v for k, v in cfg.items() if k not in SECRETS}
    for k in SECRETS:
        out[k] = {"set": bool(cfg.get(k)), "hint": f"…{cfg[k][-4:]}" if cfg.get(k) else ""}
    out["ready"] = ready(cfg)
    out["presets"] = PRESETS
    return out


def save(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    cfg = load(db)
    for k, v in values.items():
        if k not in FIELDS:
            continue
        if k in SECRETS:
            if v is None:
                cfg[k] = ""
            elif str(v).strip():
                cfg[k] = str(v).strip()
            continue                      # "" keeps the stored secret
        cfg[k] = v.strip() if isinstance(v, str) else v
    if cfg.get("provider") not in ("smtp", "brevo", "resend"):
        cfg["provider"] = "brevo"
    try:
        cfg["smtp_port"] = int(cfg.get("smtp_port") or 587)
        cfg["batch_per_minute"] = max(1, min(int(cfg.get("batch_per_minute") or 120), 1000))
    except (TypeError, ValueError):
        cfg["smtp_port"], cfg["batch_per_minute"] = 587, 120
    row = _row(db)
    if row:
        row.value = cfg
    else:
        db.add(AppSetting(key=app_settings.row_key(KEY), value=cfg))
    db.flush()
    return public(db)


def ready(cfg: dict[str, Any]) -> bool:
    if not cfg.get("from_email"):
        return False
    p = cfg.get("provider")
    if p == "smtp":
        return bool(cfg.get("smtp_host") and cfg.get("smtp_user") and cfg.get("smtp_password"))
    if p == "brevo":
        return bool(cfg.get("brevo_api_key"))
    if p == "resend":
        return bool(cfg.get("resend_api_key"))
    return False


def send(cfg: dict[str, Any], to_email: str, to_name: str, subject: str, html: str, text: str,
         headers: dict[str, str] | None = None) -> str:
    """Send one message. Returns the provider's message id (or "")."""
    if not ready(cfg):
        raise MailError("حساب الإرسال غير مضبوط — أكمل إعدادات البريد أولًا")
    headers = headers or {}
    provider = cfg["provider"]
    sender_name = cfg.get("from_name") or cfg["from_email"]
    if provider == "brevo":
        body = {"sender": {"name": sender_name, "email": cfg["from_email"]},
                "to": [{"email": to_email, **({"name": to_name} if to_name else {})}],
                "subject": subject, "htmlContent": html, "textContent": text, "headers": headers}
        if cfg.get("reply_to"):
            body["replyTo"] = {"email": cfg["reply_to"]}
        r = httpx.post("https://api.brevo.com/v3/smtp/email", json=body, timeout=30,
                       headers={"api-key": cfg["brevo_api_key"], "accept": "application/json"})
        if r.status_code >= 300:
            raise MailError(f"Brevo: {r.status_code} {r.text[:200]}")
        return (r.json() or {}).get("messageId", "")
    if provider == "resend":
        body = {"from": formataddr((sender_name, cfg["from_email"])), "to": [to_email], "subject": subject,
                "html": html, "text": text, "headers": headers}
        if cfg.get("reply_to"):
            body["reply_to"] = cfg["reply_to"]
        r = httpx.post("https://api.resend.com/emails", json=body, timeout=30,
                       headers={"Authorization": f"Bearer {cfg['resend_api_key']}"})
        if r.status_code >= 300:
            raise MailError(f"Resend: {r.status_code} {r.text[:200]}")
        return (r.json() or {}).get("id", "")
    # SMTP
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, cfg["from_email"]))
    msg["To"] = formataddr((to_name, to_email)) if to_name else to_email
    if cfg.get("reply_to"):
        msg["Reply-To"] = cfg["reply_to"]
    msg["Message-ID"] = make_msgid(domain=cfg["from_email"].split("@")[-1])
    for k, v in headers.items():
        msg[k] = v
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    try:
        if cfg.get("smtp_security") == "ssl":
            server = smtplib.SMTP_SSL(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30,
                                      context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30)
            if cfg.get("smtp_security") == "starttls":
                server.starttls(context=ssl.create_default_context())
        with server:
            server.login(cfg["smtp_user"], cfg["smtp_password"])
            server.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailError(f"SMTP: {exc}") from exc
    return msg["Message-ID"]
