import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from core.logging_config import get_logger

logger = get_logger(__name__)


def send_contact_email(name: str, email: str, subject: str, message: str) -> None:
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", "465"))
    use_ssl = os.getenv("EMAIL_USE_SSL", "1") == "1"
    user = os.getenv("EMAIL_HOST_USER")
    password = os.getenv("EMAIL_HOST_PASSWORD")
    from_email = os.getenv("DEFAULT_FROM_EMAIL", user)
    recipient = os.getenv("EMAIL_RECIPIENT")

    missing = [k for k, v in {
        "EMAIL_HOST": host,
        "EMAIL_HOST_USER": user,
        "EMAIL_HOST_PASSWORD": password,
        "EMAIL_RECIPIENT": recipient,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required email env vars: {', '.join(missing)}")

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = recipient
    msg["Subject"] = f"[Kontaktný formulár] {subject}"
    msg["Reply-To"] = email

    body = f"Meno: {name}\nEmail: {email}\n\n{message}"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.ehlo()
            server.login(user, password)
            server.sendmail(from_email, recipient, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(user, password)
            server.sendmail(from_email, recipient, msg.as_string())

    logger.info(f"Contact email sent to {recipient} (reply-to: {email})")
