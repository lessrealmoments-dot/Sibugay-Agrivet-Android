"""
Email notification service using Resend.
Handles subscription events: welcome, trial warnings, grace period, locked.
"""
import asyncio
import logging
import os
import resend
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

resend.api_key = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
PLATFORM_ADMIN_EMAIL = os.environ.get("PLATFORM_ADMIN_EMAIL", "janmarkeahig@gmail.com")
APP_NAME = "AgriBooks"
APP_URL = os.environ.get("REACT_APP_FRONTEND_URL", "https://agribooks.app")


# ---------------------------------------------------------------------------
# Core send helper
# ---------------------------------------------------------------------------
async def send_email(to: str, subject: str, html: str) -> bool:
    """Send email via Resend. Returns True on success."""
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not set — skipping email to %s", to)
        return False
    try:
        params = {"from": SENDER_EMAIL, "to": [to], "subject": subject, "html": html}
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info("Email sent to %s (id=%s) — %s", to, result.get("id"), subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False


# ---------------------------------------------------------------------------
# HTML base template
# ---------------------------------------------------------------------------
def _base(content: str, cta_url: str = "", cta_label: str = "") -> str:
    cta_block = f"""
    <div style="text-align:center;margin:32px 0;">
      <a href="{cta_url}" style="background:#10b981;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px;display:inline-block;">{cta_label}</a>
    </div>""" if cta_url else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{APP_NAME}</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:system-ui,-apple-system,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <!-- Header -->
  <tr><td style="background:#0a0f1c;padding:28px 32px;border-radius:12px 12px 0 0;">
    <table width="100%"><tr>
      <td><span style="color:#10b981;font-weight:800;font-size:20px;">AgriBooks</span></td>
      <td align="right"><span style="color:#64748b;font-size:12px;">Audit-Grade Retail Intelligence</span></td>
    </tr></table>
  </td></tr>
  <!-- Body -->
  <tr><td style="background:#ffffff;padding:36px 32px;border-radius:0 0 12px 12px;">
    {content}
    {cta_block}
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0;">
    <p style="color:#94a3b8;font-size:12px;margin:0;">
      You're receiving this because you have an account at {APP_NAME}.<br>
      Questions? Reply to this email or contact us at <a href="mailto:{PLATFORM_ADMIN_EMAIL}" style="color:#10b981;">{PLATFORM_ADMIN_EMAIL}</a>
    </p>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------

async def send_welcome(to: str, company_name: str, trial_ends: str):
    """Welcome email after registration."""
    html = _base(
        content=f"""
        <h1 style="color:#0f172a;font-size:24px;margin:0 0 8px;">Welcome to AgriBooks! 🎉</h1>
        <p style="color:#475569;font-size:15px;line-height:1.6;margin:0 0 16px;">
          Hi there,<br><br>
          <strong>{company_name}</strong> is now set up on AgriBooks with a <strong>14-day Pro trial</strong>.
          All features are unlocked — POS, Inventory, Multi-Branch, Audit Center, everything.
        </p>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:20px 0;">
          <p style="color:#166534;font-weight:600;margin:0 0 6px;">Your trial includes:</p>
          <ul style="color:#166534;margin:0;padding-left:20px;font-size:14px;line-height:1.8;">
            <li>Full POS with split payments (Cash, GCash, Maya)</li>
            <li>Multi-branch inventory & transfers</li>
            <li>Audit-grade transaction verification</li>
            <li>4-wallet fund management</li>
            <li>Unlimited users during trial</li>
          </ul>
        </div>
        <p style="color:#475569;font-size:14px;">Trial ends: <strong>{trial_ends}</strong></p>
        """,
        cta_url=APP_URL,
        cta_label="Go to Dashboard →"
    )
    await send_email(to, f"Welcome to AgriBooks — Your 14-Day Pro Trial Has Started", html)


async def send_trial_warning(to: str, company_name: str, days_left: int, trial_ends: str):
    """Warning before trial ends."""
    urgency = "🔴 URGENT" if days_left <= 1 else ("⚠️" if days_left <= 3 else "ℹ️")
    day_text = "tomorrow" if days_left == 1 else f"in {days_left} days"
    color = "#dc2626" if days_left <= 1 else ("#d97706" if days_left <= 3 else "#0369a1")
    html = _base(
        content=f"""
        <h1 style="color:{color};font-size:22px;margin:0 0 8px;">{urgency} Your trial ends {day_text}</h1>
        <p style="color:#475569;font-size:15px;line-height:1.6;">
          Hi <strong>{company_name}</strong>,<br><br>
          Your 14-day Pro trial expires on <strong>{trial_ends}</strong>.
          After that, you'll have a 3-day grace period with full access before features are locked.
        </p>
        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;margin:20px 0;">
          <p style="color:#991b1b;font-weight:600;margin:0 0 6px;">Without upgrading, you'll lose:</p>
          <ul style="color:#991b1b;margin:0;padding-left:20px;font-size:14px;line-height:1.8;">
            <li>Purchase Orders & Supplier Management</li>
            <li>Multi-Branch Transfers</li>
            <li>Full Audit Center & Verification</li>
            <li>Employee Management</li>
          </ul>
        </div>
        <p style="color:#475569;font-size:14px;">
          Upgrade to keep everything running. Plans start at ₱1,500/month ($30).
        </p>
        """,
        cta_url=f"{APP_URL}/upgrade",
        cta_label="Upgrade Now — Keep All Features"
    )
    await send_email(to, f"[{urgency}] Your AgriBooks trial ends {day_text} — Upgrade to keep access", html)


async def send_grace_period_warning(to: str, company_name: str, days_left: int, locked_date: str):
    """During the 3-day grace period after expiry."""
    day_text = "today" if days_left == 0 else (f"in {days_left} day{'s' if days_left > 1 else ''}")
    html = _base(
        content=f"""
        <h1 style="color:#dc2626;font-size:22px;margin:0 0 8px;">🔒 Features lock {day_text}</h1>
        <p style="color:#475569;font-size:15px;line-height:1.6;">
          Hi <strong>{company_name}</strong>,<br><br>
          Your subscription has expired. You are currently in your <strong>3-day grace period</strong>.
          All features are still accessible, but <strong>your account will be locked on {locked_date}</strong>
          unless you renew.
        </p>
        <div style="background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:16px;margin:20px 0;">
          <p style="color:#854d0e;font-weight:600;margin:0;">
            To renew: Go to your Upgrade page, select a plan, and send payment to our accounts.
            Your access will be restored within 24 hours of payment confirmation.
          </p>
        </div>
        """,
        cta_url=f"{APP_URL}/upgrade",
        cta_label="Renew Now →"
    )
    await send_email(to, f"[ACTION NEEDED] AgriBooks account locks {day_text} — Renew to keep access", html)


async def send_account_locked(to: str, company_name: str):
    """Sent when account is fully locked."""
    html = _base(
        content=f"""
        <h1 style="color:#dc2626;font-size:22px;margin:0 0 8px;">🔒 Your AgriBooks account is locked</h1>
        <p style="color:#475569;font-size:15px;line-height:1.6;">
          Hi <strong>{company_name}</strong>,<br><br>
          Your subscription has expired and the 3-day grace period has ended.
          <strong>Your account is now locked</strong> — data is preserved safely, but access is suspended
          until you renew.
        </p>
        <p style="color:#475569;font-size:14px;">
          All your data (products, customers, sales, invoices) is secure and will be fully restored
          when you reactivate your subscription.
        </p>
        """,
        cta_url=f"{APP_URL}/upgrade",
        cta_label="Reactivate Account →"
    )
    await send_email(to, "Your AgriBooks account has been locked — Reactivate to restore access", html)


async def send_subscription_activated(to: str, company_name: str, plan: str, expires: str = ""):
    """Sent when admin activates/upgrades subscription."""
    plan_cap = plan.capitalize()
    html = _base(
        content=f"""
        <h1 style="color:#10b981;font-size:22px;margin:0 0 8px;">✅ Subscription Activated!</h1>
        <p style="color:#475569;font-size:15px;line-height:1.6;">
          Hi <strong>{company_name}</strong>,<br><br>
          Your <strong>{plan_cap} plan</strong> has been activated. All features for your plan are now
          available.
        </p>
        {f'<p style="color:#475569;font-size:14px;">Next renewal: <strong>{expires}</strong></p>' if expires else ''}
        <p style="color:#475569;font-size:14px;">
          Thank you for your business. If you have any questions, reply to this email.
        </p>
        """,
        cta_url=APP_URL,
        cta_label="Go to Dashboard →"
    )
    await send_email(to, f"AgriBooks {plan_cap} Plan Activated — Welcome!", html)


async def send_superadmin_backup_codes(to: str, codes: list):
    """Send backup recovery codes to super admin."""
    codes_html = "".join(
        f'<div style="font-family:monospace;font-size:16px;letter-spacing:2px;background:#f1f5f9;padding:8px 16px;margin:4px 0;border-radius:6px;color:#0f172a;">{code}</div>'
        for code in codes
    )
    html = _base(
        content=f"""
        <h1 style="color:#0f172a;font-size:22px;margin:0 0 8px;">🔐 Your Recovery Backup Codes</h1>
        <p style="color:#475569;font-size:15px;line-height:1.6;">
          These are your one-time backup codes for the AgriBooks Platform Admin panel.
          Store them somewhere safe (password manager, printed copy in a secure place).
        </p>
        <div style="background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:12px 16px;margin:16px 0;">
          <p style="color:#854d0e;font-weight:600;margin:0;font-size:13px;">
            ⚠️ Each code can only be used ONCE. Once used, it's invalid. Keep these secret.
          </p>
        </div>
        {codes_html}
        <p style="color:#94a3b8;font-size:13px;margin-top:16px;">
          If you lose your Google Authenticator access, use one of these codes to log in.
        </p>
        """
    )
    await send_email(to, "AgriBooks Platform Admin — Your Recovery Backup Codes", html)


async def send_new_registration_admin_alert(to: str, company_name: str, owner_email: str, plan: str = "trial"):
    """Notify platform admin when a new company registers."""
    html = _base(
        content=f"""
        <h1 style="color:#0f172a;font-size:22px;margin:0 0 8px;">New Company Registration</h1>
        <p style="color:#475569;font-size:15px;line-height:1.6;">
          A new company has registered on AgriBooks and started their 14-day trial.
        </p>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:20px 0;">
          <table style="width:100%;font-size:14px;">
            <tr><td style="color:#64748b;padding:4px 0;">Company:</td><td style="color:#0f172a;font-weight:600;">{company_name}</td></tr>
            <tr><td style="color:#64748b;padding:4px 0;">Owner Email:</td><td style="color:#0f172a;">{owner_email}</td></tr>
            <tr><td style="color:#64748b;padding:4px 0;">Plan:</td><td style="color:#10b981;font-weight:600;">{plan.capitalize()} Trial</td></tr>
          </table>
        </div>
        <p style="color:#475569;font-size:14px;">
          Review this account in the Super Admin panel if needed.
        </p>
        """,
        cta_url=f"{APP_URL}/superadmin",
        cta_label="View in Admin Panel →"
    )
    await send_email(to, f"New Registration: {company_name} has joined AgriBooks", html)


async def send_subscription_rejected(to: str, company_name: str, plan: str, reason: str):
    """Notify customer when subscription payment is rejected."""
    plan_cap = plan.capitalize()
    html = _base(
        content=f"""
        <h1 style="color:#dc2626;font-size:22px;margin:0 0 8px;">Subscription Payment Not Confirmed</h1>
        <p style="color:#475569;font-size:15px;line-height:1.6;">
          Hi <strong>{company_name}</strong>,<br><br>
          Unfortunately, we were unable to confirm your payment for the <strong>{plan_cap} Plan</strong>.
        </p>
        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;margin:20px 0;">
          <p style="color:#991b1b;font-weight:600;margin:0 0 6px;">Reason:</p>
          <p style="color:#991b1b;margin:0;font-size:14px;">{reason}</p>
        </div>
        <p style="color:#475569;font-size:14px;line-height:1.6;">
          Please resubmit your payment proof via the Upgrade page, ensuring:
        </p>
        <ul style="color:#475569;font-size:14px;padding-left:20px;line-height:1.8;">
          <li>The exact amount is visible on the screenshot</li>
          <li>Your company name is included as payment reference</li>
          <li>The payment receipt is clear and unedited</li>
        </ul>
        <p style="color:#475569;font-size:14px;">
          If you believe this is an error, reply to this email with your payment details.
        </p>
        """,
        cta_url=f"{APP_URL}/upgrade",
        cta_label="Resubmit Payment Proof →"
    )
    await send_email(to, f"AgriBooks: Payment Not Confirmed for {plan_cap} Plan", html)
