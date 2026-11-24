# ruff: noqa: E501 — HTML de e-mail usa estilos inline longos.
from html import escape

from app.modules.notifications.email import EmailMessage


def _layout(title: str, greeting: str, body: str, cta_label: str, cta_url: str, footer: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR"><body style="margin:0;background:#fff7ed;font-family:Arial,sans-serif;color:#1f2937">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px">
<table role="presentation" width="100%" style="max-width:480px;background:#fff;border-radius:16px;padding:32px">
<tr><td style="font-size:28px;text-align:center">🎁</td></tr>
<tr><td><h1 style="font-size:22px;margin:8px 0 16px;text-align:center">{escape(title)}</h1>
<p style="font-size:16px;line-height:1.5">{escape(greeting)}</p>
<p style="font-size:16px;line-height:1.5">{escape(body)}</p>
<p style="text-align:center;margin:28px 0"><a href="{escape(cta_url)}"
 style="background:#e11d48;color:#fff;text-decoration:none;padding:14px 24px;border-radius:999px;font-weight:bold;display:inline-block">{escape(cta_label)}</a></p>
<p style="font-size:13px;color:#6b7280;line-height:1.5">{escape(footer)}</p>
<p style="font-size:12px;color:#9ca3af;word-break:break-all">{escape(cta_url)}</p>
</td></tr></table></td></tr></table></body></html>"""


def verify_email(to: str, name: str, url: str) -> EmailMessage:
    title = "Confirme seu e-mail"
    greeting = f"Oi, {name}!"
    body = "Falta só um passo para você criar e participar de amigos secretos no Tirei Você!"
    footer = "O link vale por 24 horas. Se você não criou uma conta, ignore este e-mail."
    return EmailMessage(
        to=to,
        subject="Confirme seu e-mail no Tirei Você! 🎁",
        html=_layout(title, greeting, body, "Confirmar e-mail", url, footer),
        text=f"{greeting}\n\n{body}\n\nConfirme seu e-mail: {url}\n\n{footer}",
    )


def reset_password(to: str, name: str, url: str) -> EmailMessage:
    title = "Redefinir sua senha"
    greeting = f"Oi, {name}!"
    body = "Recebemos um pedido para redefinir a senha da sua conta no Tirei Você!"
    footer = (
        "O link vale por 1 hora. Se não foi você, ignore este e-mail: sua senha continua a mesma."
    )
    return EmailMessage(
        to=to,
        subject="Redefinição de senha — Tirei Você!",
        html=_layout(title, greeting, body, "Criar nova senha", url, footer),
        text=f"{greeting}\n\n{body}\n\nCrie uma nova senha: {url}\n\n{footer}",
    )
