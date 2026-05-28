import smtplib
from email.message import EmailMessage

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD


def send_email(to_address, subject, body):
    """Send a plain-text email via Gmail SMTP with STARTTLS."""
    msg = EmailMessage()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
