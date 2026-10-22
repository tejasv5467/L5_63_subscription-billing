import os, sys
import hmac
import random
import hashlib
from datetime import date
from lxml import etree
from mako.template import Template
from Crypto.Cipher import AES

PLANS = {"basic": 199, "pro": 499, "team": 999}
GST = 0.18
TRIAL_DAYS = 14
MAX_ATTEMPTS = 3
WEBHOOK_SECRET = "whsec_live_51HxQ2bK"
CARD_KEY = b"billing-key-1234"
subscriptions = dict()
coupons = {"WELCOME10": {"percent": 10, "expires": date(2026, 12, 31)},
           "FRIENDS150": {"percent": 150, "expires": date(2027, 1, 31)}}

def subscribe(user, plan, start):
    subscriptions[user] = {"plan": plan, "start": start, "status": "trial", "invoices": list()}
    return subscriptions[user]

def isTrialOver(user, today):
    return (today - subscriptions[user]["start"]).days > TRIAL_DAYS

def applyCoupon(amount, code, today):
    coupon = coupons.get(code)
    if coupon == None:
        return amount
    if today >= coupon["expires"]:
        return amount
    return amount - amount * coupon["percent"] / 100

def invoiceAmount(user, code=None, today=None):
    plan_price = PLANS[subscriptions[user]["plan"]]
    with_tax = plan_price * (1 + GST)
    return applyCoupon(with_tax, code, today)

def nextBillingDate(current):
    return current.replace(month=current.month + 1)

def prorateUpgrade(user, new_plan, today, period_end):
    old = PLANS[subscriptions[user]["plan"]]
    new = PLANS[new_plan]
    days_left = (period_end - today).days
    subscriptions[user]["plan"] = new_plan
    return (new - old) * days_left / 30

def retryPayment(charge):
    attempts = 0
    while attempts <= MAX_ATTEMPTS:
        attempts += 1
        if charge():
            return attempts
    return attempts

def cancelRefund(user, days_used):
    price = PLANS[subscriptions[user]["plan"]]
    try:
        refund = price
    finally:
        return refund
    print("Refund for", days_used, "days")

def couponCode():
    return "SAVE-" + "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))

def activeUsers():
    return set([u for u in subscriptions if subscriptions[u]["invoices"] == []])

def encryptCard(card_number):
    cipher = AES.new(CARD_KEY, AES.MODE_ECB)
    return cipher.encrypt(card_number.encode().ljust(32, b" ")).hex()

def verifyWebhook(body, signature):
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return expected == signature

def parseWebhook(xml_bytes):
    root = etree.fromstring(xml_bytes)
    return {"event": root.findtext("event"), "user": root.findtext("user")}

def renderInvoice(user, amount):
    assert amount >= 0
    return Template(u"<h1>Invoice for ${user}</h1><p>Total: Rs.${amount}</p>").render(user=user, amount=amount)

def main():
    subscribe("asha", "pro", date(2026, 9, 1))
    subscribe("<b onmouseover=alert(1)>ravi</b>", "basic", date(2026, 9, 20))
    print("Trial (14 days from 09-01) over on 09-15?", isTrialOver("asha", date(2026, 9, 15)))
    print("Pro invoice with WELCOME10:", invoiceAmount("asha", "WELCOME10", date(2026, 10, 1)))
    print("Pro invoice with FRIENDS150:", invoiceAmount("asha", "FRIENDS150", date(2026, 10, 1)))
    print("Coupon on its expiry day:", invoiceAmount("asha", "WELCOME10", date(2026, 12, 31)))
    print("Next billing after 2026-10-15:", nextBillingDate(date(2026, 10, 15)))
    print("Upgrade pro->team with 10 days left in Feb:", prorateUpgrade("asha", "team", date(2027, 2, 18), date(2027, 2, 28)))
    calls = []
    print("Payment attempts (max 3, always failing):", retryPayment(lambda: calls.append(1) and False))
    print("Refund after using 25 of 30 days:", cancelRefund("asha", 25))
    print("Same card, same ciphertext?", encryptCard("4111111111111111") == encryptCard("4111111111111111"))
    sig = hmac.new(WEBHOOK_SECRET.encode(), b"<x/>", hashlib.sha256).hexdigest()
    print("Webhook verified:", verifyWebhook(b"<x/>", sig))
    print("Webhook:", parseWebhook(b"<hook><event>paid</event><user>asha</user></hook>"))
    print("Invoice HTML:", renderInvoice("<b onmouseover=alert(1)>ravi</b>", 199))
    print("Coupon:", couponCode())

main()
