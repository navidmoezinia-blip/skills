"""Send the brief via Gmail. Standard library only (smtplib).

Use a Gmail **App Password** (Google Account -> Security -> 2-Step Verification
-> App passwords), not your normal password.
"""

import smtplib
import ssl
from email.message import EmailMessage


def send(subject: str, html_body: str, text_body: str, to_addr: str,
         gmail_user: str, app_password: str) -> None:
    if not (gmail_user and app_password and to_addr):
        raise ValueError("gmail_user, app_password and to_addr are all required.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_addr
    msg.set_content(text_body or "See HTML version.")
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(gmail_user, app_password)
        server.send_message(msg)
