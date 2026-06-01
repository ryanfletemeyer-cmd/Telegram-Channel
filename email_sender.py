import socket
import smtplib
from email.message import EmailMessage

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD

# Force IPv4 — Railway containers often fail on IPv6 routes to smtp.gmail.com
_orig_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_ipv4(*args, **kwargs):
    results = _orig_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in results if r[0] == socket.AF_INET]
    return ipv4 if ipv4 else results


socket.getaddrinfo = _getaddrinfo_ipv4


def send_email(to_address, subject, body):
    """Send a plain-text email via Gmail SMTP with STARTTLS."""
    msg = EmailMessage()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
