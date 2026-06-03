import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from app.config import settings

logger = logging.getLogger(__name__)


def _send_smtp(to: str, subject: str, body_text: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    # Extract plain email for SMTP envelope — display names with <"email"> break Gmail
    _, sender_email = parseaddr(settings.SMTP_FROM)
    sender_email = sender_email.strip('"')

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(sender_email, to, msg.as_string())


def _build_activation_html(token: str, bot_username: str, deep_link: str) -> str:
    btn = (
        f'<a href="{deep_link}" style="display:inline-block;background:#16a34a;color:#ffffff;'
        f'text-decoration:none;padding:14px 32px;border-radius:10px;font-weight:700;'
        f'font-size:16px;margin:8px 0;">Activar mi cuenta en Telegram →</a>'
        if deep_link else ""
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Activa tu cuenta de NegocioSano</title>
</head>
<body style="margin:0;padding:0;background:#f0fdf4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fdf4;padding:40px 16px;">
    <tr><td align="center">

      <!-- Card -->
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);max-width:100%;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#16a34a,#15803d);padding:36px 40px;text-align:center;">
            <p style="margin:0;font-size:28px;">🌿</p>
            <h1 style="margin:8px 0 0;color:#ffffff;font-size:22px;font-weight:800;letter-spacing:-0.5px;">NegocioSano</h1>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <h2 style="margin:0 0 12px;color:#111827;font-size:20px;font-weight:700;">¡Bienvenido a NegocioSano! 🎉</h2>
            <p style="margin:0 0 24px;color:#6b7280;font-size:15px;line-height:1.6;">
              Tu suscripción está activa. Solo necesitas un paso más para empezar a recibir alertas de tus reseñas de Google.
            </p>

            <!-- Steps -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border-radius:12px;padding:20px;margin-bottom:28px;">
              <tr>
                <td style="padding:8px 0;color:#374151;font-size:14px;line-height:1.6;">
                  <span style="background:#16a34a;color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;margin-right:10px;padding:2px 7px;">1</span>
                  Haz clic en el botón de abajo para abrir Telegram
                </td>
              </tr>
              <tr>
                <td style="padding:8px 0;color:#374151;font-size:14px;line-height:1.6;">
                  <span style="background:#16a34a;color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;margin-right:10px;padding:2px 7px;">2</span>
                  El bot te activará automáticamente
                </td>
              </tr>
              <tr>
                <td style="padding:8px 0;color:#374151;font-size:14px;line-height:1.6;">
                  <span style="background:#16a34a;color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;margin-right:10px;padding:2px 7px;">3</span>
                  Añade tu negocio con <code style="background:#f0fdf4;color:#15803d;padding:2px 6px;border-radius:4px;font-size:13px;">/agregar</code> y listo
                </td>
              </tr>
            </table>

            <!-- CTA Button -->
            <div style="text-align:center;margin-bottom:28px;">
              {btn}
            </div>

            <!-- Token fallback -->
            <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:20px;margin-bottom:24px;">
              <p style="margin:0 0 10px;color:#6b7280;font-size:13px;">Si el botón no funciona, envía este comando a <strong>@{bot_username}</strong> en Telegram:</p>
              <code style="display:block;background:#111827;color:#4ade80;padding:14px 16px;border-radius:8px;font-size:14px;letter-spacing:0.5px;word-break:break-all;">/activar {token}</code>
            </div>

            <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center;">Este enlace caduca en 48 horas.</p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:20px 40px;text-align:center;">
            <p style="margin:0;color:#9ca3af;font-size:12px;">
              NegocioSano · Gestión de reputación online para negocios españoles<br>
              ¿Dudas? Escríbenos a <a href="mailto:hola@negociosano.com" style="color:#16a34a;text-decoration:none;">hola@negociosano.com</a>
            </p>
          </td>
        </tr>

      </table>
      <!-- /Card -->

    </td></tr>
  </table>
</body>
</html>"""


async def send_activation_email(to: str, token: str) -> None:
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured — skipping activation email for %s", to)
        return

    if not token:
        logger.error("send_activation_email called with empty token for %s", to)
        return

    bot_username = settings.BOT_USERNAME
    deep_link = f"https://t.me/{bot_username}?start={token}" if bot_username else ""

    subject = "Activa tu cuenta de NegocioSano"

    body_text = (
        f"Bienvenido a NegocioSano.\n\n"
        f"Tu token de activación es: {token}\n\n"
        f"Abre Telegram y envía este mensaje a @{bot_username}:\n"
        f"/activar {token}\n\n"
        + (f"O activa directamente: {deep_link}\n\n" if deep_link else "")
        + "El enlace caduca en 48 horas.\n\n"
        "NegocioSano — hola@negociosano.com"
    )

    body_html = _build_activation_html(token, bot_username, deep_link)

    try:
        await asyncio.to_thread(_send_smtp, to, subject, body_text, body_html)
        logger.info("Activation email sent to %s", to)
    except Exception:
        logger.exception("Failed to send activation email to %s", to)
