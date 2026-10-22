import secrets
import string
import html
import os
import hmac
import hashlib
from cryptography.fernet import Fernet
from datetime import date
from lxml import etree
PLANS = {"basic": 199, "pro": 499, "team": 999}
GST = 0.18
TRIAL_DAYS = 14
MAX_ATTEMPTS = 3
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
CARD_KEY = os.environ.get("CARD_KEY")
subscriptions = dict()
coupons = {"WELCOME10": {"percent": 10, "expires": date(2026, 12, 31)},
           "FRIENDS150": {"percent": 150, "expires": date(2027, 1, 31)}}


def subscribe(user, plan, start):
    subscriptions[user] = {
        "plan": plan,
        "start": start,
        "status": "trial",
        "invoices": list()}
    return subscriptions[user]


def is_trial_over(user, today):
    return (today - subscriptions[user]["start"]).days > TRIAL_DAYS


def apply_coupon(amount, code, today):
    coupon = coupons.get(code)

    if coupon is None:
        return amount

    if today >= coupon["expires"]:
        return amount

    percent = coupon["percent"]
    if not 0 <= percent <= 100:
        return amount

    return max(0, amount - amount * percent / 100)


def invoice_amount(user, code=None, today=None):
    plan_price = PLANS[subscriptions[user]["plan"]]
    with_tax = plan_price * (1 + GST)
    return apply_coupon(with_tax, code, today)


def next_billing_date(current):
    if current.month == 12:
        return current.replace(
            year=current.year + 1,
            month=1,
        )
    return current.replace(month=current.month + 1)


def prorate_upgrade(user, new_plan, today, period_end):
    old = PLANS[subscriptions[user]["plan"]]
    new = PLANS[new_plan]
    days_left = (period_end - today).days
    subscriptions[user]["plan"] = new_plan
    return (new - old) * days_left / 30


def retry_payment(charge):
    attempts = 0

    while attempts < MAX_ATTEMPTS:
        attempts += 1

        if charge():
            return attempts

    return attempts


def cancel_refund(user, days_used):
    price = PLANS[subscriptions[user]["plan"]]
    total_days = 30
    days_used = max(0, min(days_used, total_days))
    unused_days = total_days - days_used

    return round(price * unused_days / total_days, 2)


def coupon_code():
    alphabet = string.ascii_uppercase + string.digits
    code = "".join(
        secrets.choice(alphabet) for _ in range(6)
    )
    return f"SAVE-{code}"


def active_users():
    return set([u for u in subscriptions if subscriptions[u]["invoices"] == []])


def encrypt_card(card_number):
    key = os.environ.get("CARD_KEY")

    if not key:
        raise ValueError("CARD_KEY environment variable is required")

    try:
        fernet = Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ValueError("CARD_KEY must be a valid Fernet key") from exc

    return fernet.encrypt(str(card_number).encode("utf-8")).decode("utf-8")


def verify_webhook(body, signature):
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256).hexdigest()
    return expected == signature


def parse_webhook(xml_bytes):
    root = etree.fromstring(xml_bytes)
    return {"event": root.findtext("event"), "user": root.findtext("user")}


def render_invoice(user, amount):
    if amount < 0:
        raise ValueError("Invoice amount cannot be negative")

    safe_user = html.escape(str(user))
    safe_amount = html.escape(str(amount))

    return (
        f"<h1>Invoice for {safe_user}</h1>"
        f"<p>Total: Rs.{safe_amount}</p>"
    )


def main():
    subscribe("asha", "pro", date(2026, 9, 1))
    subscribe("<b onmouseover=alert(1)>ravi</b>", "basic", date(2026, 9, 20))
    print("Trial (14 days from 09-01) over on 09-15?",
          is_trial_over("asha", date(2026, 9, 15)))
    print(
        "Pro invoice with WELCOME10:",
        invoice_amount(
            "asha",
            "WELCOME10",
            date(
                2026,
                10,
                1)))
    print(
        "Pro invoice with FRIENDS150:",
        invoice_amount(
            "asha",
            "FRIENDS150",
            date(
                2026,
                10,
                1)))
    print(
        "Coupon on its expiry day:",
        invoice_amount(
            "asha",
            "WELCOME10",
            date(
                2026,
                12,
                31)))
    print(
        "Next billing after 2026-10-15:",
        next_billing_date(
            date(
                2026,
                10,
                15)))
    print(
        "Upgrade pro->team with 10 days left in Feb:",
        prorate_upgrade(
            "asha",
            "team",
            date(
                2027,
                2,
                18),
            date(
                2027,
                2,
                28)))
    calls = []
    print("Payment attempts (max 3, always failing):",
          retry_payment(lambda: calls.append(1) and False))
    print("Refund after using 25 of 30 days:", cancel_refund("asha", 25))
    print("Same card, same ciphertext?", encrypt_card(
        "4111111111111111") == encrypt_card("4111111111111111"))
    sig = hmac.new(
        WEBHOOK_SECRET.encode(),
        b"<x/>",
        hashlib.sha256).hexdigest()
    print("Webhook verified:", verify_webhook(b"<x/>", sig))
    print("Webhook:", parse_webhook(
        b"<hook><event>paid</event><user>asha</user></hook>"))
    print(
        "Invoice HTML:",
        render_invoice(
            "<b onmouseover=alert(1)>ravi</b>",
            199))
    print("Coupon:", coupon_code())


main()
