# app/utils/email.py
# Email sending service using SMTP.
# Add SMTP settings to your .env when ready to send real emails.

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings
from app.core.logging import logger


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Internal helper that sends an email via SMTP."""
    # Add these to your .env when you have an SMTP provider (SendGrid, SES, etc.)
    smtp_host = getattr(settings, "SMTP_HOST", None)
    smtp_port = getattr(settings, "SMTP_PORT", 587)
    smtp_user = getattr(settings, "SMTP_USER", None)
    smtp_password = getattr(settings, "SMTP_PASSWORD", None)
    from_email = getattr(settings, "FROM_EMAIL", "noreply@savourystudio.com")

    if not smtp_host:
        # Dev mode: just log the email instead of sending
        logger.info(f"[EMAIL - DEV MODE] To: {to_email} | Subject: {subject}")
        logger.debug(f"[EMAIL BODY] {html_body}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_welcome_email(to_email: str, name: str) -> bool:
    subject = f"Welcome to {settings.APP_NAME}!"
    body = f"""
    <h2>Welcome, {name}!</h2>
    <p>Your account has been created successfully.</p>
    <p>Start exploring our services today.</p>
    """
    return _send_email(to_email, subject, body)


def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    reset_url = f"http://localhost:3000/reset-password?token={reset_token}"
    subject = "Reset Your Password"
    body = f"""
    <h2>Password Reset Request</h2>
    <p>Click the link below to reset your password. This link expires in 1 hour.</p>
    <a href="{reset_url}">Reset Password</a>
    <p>If you did not request this, ignore this email.</p>
    """
    return _send_email(to_email, subject, body)


def send_booking_confirmation_email(to_email: str, name: str, booking_id: int) -> bool:
    subject = f"Booking Confirmed - #{booking_id}"
    body = f"""
    <h2>Hi {name}, your booking is confirmed!</h2>
    <p>Booking reference: <strong>#{booking_id}</strong></p>
    <p>You can track your booking status in the app.</p>
    """
    return _send_email(to_email, subject, body)


def send_vendor_approval_email(to_email: str, business_name: str, approved: bool, reason: Optional[str] = None) -> bool:
    if approved:
        subject = "Your Vendor Account is Approved!"
        body = f"<h2>Congratulations!</h2><p>Your vendor account <strong>{business_name}</strong> has been approved. You can now start listing your services.</p>"
    else:
        subject = "Vendor Application Update"
        body = f"<h2>Application Not Approved</h2><p>Your vendor account <strong>{business_name}</strong> was not approved.</p>"
        if reason:
            body += f"<p><strong>Reason:</strong> {reason}</p>"
        body += "<p>Please contact support if you have questions.</p>"
    return _send_email(to_email, subject, body)