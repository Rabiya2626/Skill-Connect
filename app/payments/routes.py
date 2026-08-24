import hashlib
import hmac
import json
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import csrf, db
from app.models import Notification, Payment, Session
from app.payments import payments_bp


def _razorpay_request(path, payload):
    credentials = f"{current_app.config['RAZORPAY_KEY_ID']}:{current_app.config['RAZORPAY_KEY_SECRET']}".encode()
    import base64
    request_data = json.dumps(payload).encode()
    api_request = Request(f"https://api.razorpay.com/v1/{path}", data=request_data, method="POST", headers={
        "Authorization": f"Basic {base64.b64encode(credentials).decode()}", "Content-Type": "application/json",
    })
    with urlopen(api_request, timeout=15) as response:
        return json.loads(response.read().decode())


@payments_bp.post("/sessions/<int:session_id>/checkout")
@login_required
def checkout(session_id):
    session = Session.query.filter_by(id=session_id, learner_id=current_user.id, status="confirmed").first_or_404()
    if session.is_skill_exchange:
        flash("This session is a skill exchange and does not need payment.", "warning")
        return redirect(url_for("sessions.index"))
    if current_app.config["PAYMENT_MODE"] != "sandbox" or not current_app.config["RAZORPAY_KEY_ID"] or not current_app.config["RAZORPAY_KEY_SECRET"]:
        flash("Razorpay sandbox is not configured yet.", "error")
        return redirect(url_for("sessions.index"))
    payment = Payment.query.filter_by(session_id=session.id).first()
    if payment and payment.status == "paid":
        return redirect(url_for("payments.receipt", payment_id=payment.id))
    amount = current_app.config["SESSION_PRICE_PAISE"]
    try:
        order = _razorpay_request("orders", {"amount": amount, "currency": "INR", "receipt": f"sc-{session.id}-{uuid4().hex[:8]}", "payment_capture": 1})
    except (HTTPError, URLError, OSError, ValueError):
        current_app.logger.exception("Unable to create Razorpay test order")
        flash("Could not create the Razorpay test order. Check your sandbox keys.", "error")
        return redirect(url_for("sessions.index"))
    if not payment:
        payment = Payment(session_id=session.id, payer_id=current_user.id, amount_paise=amount, receipt_number=order["receipt"], provider="razorpay")
        db.session.add(payment)
    payment.provider_reference = order["id"]
    payment.status = "pending"
    db.session.commit()
    return render_template("payments/checkout.html", session=session, payment=payment, order_id=order["id"], key_id=current_app.config["RAZORPAY_KEY_ID"], active_nav="sessions")


@payments_bp.post("/payments/verify")
@csrf.exempt
def verify_payment():
    order_id = request.form.get("razorpay_order_id", "")
    payment_id = request.form.get("razorpay_payment_id", "")
    signature = request.form.get("razorpay_signature", "")
    payment = Payment.query.filter_by(provider_reference=order_id, status="pending").first_or_404()
    signed = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(current_app.config["RAZORPAY_KEY_SECRET"].encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        abort(400)
    payment.status = "paid"
    payment.provider_reference = payment_id
    db.session.add(Notification(user_id=payment.session.tutor_id, type="payment_received", message="A session payment was completed in Razorpay test mode.", session_id=payment.session_id))
    db.session.commit()
    return redirect(url_for("payments.receipt", payment_id=payment.id))


@payments_bp.post("/webhooks/razorpay")
@csrf.exempt
def razorpay_webhook():
    """Validate Razorpay's test webhook before touching local payment state."""
    secret = current_app.config["RAZORPAY_WEBHOOK_SECRET"]
    body = request.get_data()
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest() if secret else ""
    if not secret or not hmac.compare_digest(expected, signature):
        abort(400)
    payload = request.get_json(silent=True) or {}
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    payment = Payment.query.filter_by(provider_reference=order_id).first()
    if payment and payload.get("event") == "payment.captured":
        payment.status = "paid"
        db.session.commit()
    return "", 200


@payments_bp.post("/payments/<int:payment_id>/refund")
@login_required
def refund(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if current_user.id != payment.payer_id or payment.status != "paid":
        abort(403)
    try:
        _razorpay_request(f"payments/{payment.provider_reference}/refund", {"amount": payment.amount_paise})
    except (HTTPError, URLError, OSError, ValueError):
        current_app.logger.exception("Unable to create Razorpay test refund")
        flash("Could not start the Razorpay test refund.", "error")
        return redirect(url_for("payments.receipt", payment_id=payment.id))
    payment.status = "refunded"
    db.session.commit()
    flash("Razorpay test refund started.", "success")
    return redirect(url_for("payments.receipt", payment_id=payment.id))


@payments_bp.get("/payments/<int:payment_id>/receipt")
@login_required
def receipt(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if current_user.id not in {payment.payer_id, payment.session.tutor_id}:
        abort(403)
    return render_template("payments/receipt.html", payment=payment, active_nav="sessions")
