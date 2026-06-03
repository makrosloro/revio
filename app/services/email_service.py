import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _send_smtp(to: str, subject: str, body_text: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, to, msg.as_string())


async def send_activation_email(to: str, token: str) -> None:
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured — skipping activation email for %s", to)
        return

    bot_username = settings.BOT_USERNAME
    deep_link = f"https://t.me/{bot_username}?start={token}" if bot_username else ""

    subject = "Activa tu cuenta de NegocioSano"

    body_text = (
        f"Hola,\n\n"
        f"Gracias por suscribirte a NegocioSano.\n\n"
        f"Tu token de activación es:\n{token}\n\n"
        f"Para activar tu cuenta, abre Telegram y envía este mensaje a @{bot_username}:\n"
        f"/activar {token}\n\n"
        + (f"O haz clic aquí para activar directamente:\n{deep_link}\n\n" if deep_link else "")
        + "El token caduca en 48 horas.\n\n"
        "NegocioSano"
    )

    body_html = f"""
    <p>Hola,</p>
    <p>Gracias por suscribirte a <strong>NegocioSano</strong>.</p>
    <p>Tu token de activación es:<br>
    <code style="font-size:1.2em">{token}</code></p>
    <p>Abre Telegram y envía este mensaje a @{bot_username}:<br>
    <code>/activar {token}</code></p>
    {f'<p><a href="{deep_link}">Haz clic aquí para activar directamente en Telegram</a></p>' if deep_link else ''}
    <p><small>El token caduca en 48 horas.</small></p>
    <p>NegocioSano</p>
    """

    try:
        await asyncio.to_thread(_send_smtp, to, subject, body_text, body_html)
        logger.info("Activation email sent to %s", to)
    except Exception:
        logger.exception("Failed to send activation email to %s", to)
