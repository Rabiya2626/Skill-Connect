from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.utils import secure_filename

from app.auth.forms import LoginForm, PasswordResetForm, PasswordResetRequestForm, ProfileForm, RegistrationForm
from app.extensions import db
from app.models import Learner, Notification, Tutor, User
from app.services.email import send_email

auth_bp = Blueprint("auth", __name__)
ALLOWED_PROFILE_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _token_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="skillconnect-account")


def _account_token(user, purpose):
    payload = {"user_id": user.id, "purpose": purpose}
    # A reset token is single-use: changing the password changes this value.
    if purpose == "reset":
        payload["password_hash"] = user.password_hash
    return _token_serializer().dumps(payload)


def _user_from_token(token, purpose, max_age=3600):
    try:
        payload = _token_serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if payload.get("purpose") != purpose:
        return None
    user = db.session.get(User, payload.get("user_id"))
    if purpose == "reset" and (not user or payload.get("password_hash") != user.password_hash):
        return None
    return user


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(name=form.name.data.strip(), email=form.email.data.lower(), role=form.role.data, bio=form.bio.data.strip(), terms_accepted_at=datetime.utcnow())
        user.set_password(form.password.data)
        db.session.add(user)
        if user.role in {"learner", "both"}:
            user.learner = Learner()
        if user.role in {"tutor", "both"}:
            user.tutor = Tutor()
        db.session.commit()
        verification_url = url_for("auth.verify_email", token=_account_token(user, "verify"), _external=True)
        send_email(user.email, "Verify your SkillConnect email", f"<p>Welcome to SkillConnect.</p><p><a href=\"{verification_url}\">Verify your email</a></p>")
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("dashboard.index"))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.home"))


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    user = _user_from_token(token, "verify", max_age=86400)
    if not user:
        flash("That verification link is invalid or has expired.", "error")
    else:
        user.is_verified = True
        db.session.commit()
        flash("Your email has been verified.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            reset_url = url_for("auth.reset_password", token=_account_token(user, "reset"), _external=True)
            email_html = f"""<div style=\"font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#14213D\"><h1>SkillConnect</h1><p>Hello {user.name},</p><p>We received a request to reset your password.</p><p><a href=\"{reset_url}\" style=\"display:inline-block;padding:12px 18px;background:#E8A23D;color:#14213D;text-decoration:none;border-radius:6px;font-weight:bold\">Reset Password</a></p><p>This password reset link will expire after a limited period. If you did not request it, you can safely ignore this email.</p></div>"""
            delivered = send_email(user.email, "Reset your SkillConnect password", email_html)
            if not delivered:
                current_app.logger.warning("Password reset requested for %s but no email was delivered; configure Resend to enable delivery.", user.email)
        flash("If an account exists for this email, a password reset link has been sent.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = _user_from_token(token, "reset")
    form = PasswordResetForm()
    if not user:
        return render_template("auth/reset_password.html", form=form, invalid_token=True)
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, invalid_token=False)


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if request.method == "GET" and current_user.learner:
        form.learning_goals.data = current_user.learner.learning_goals
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.bio = form.bio.data.strip()
        uploaded = request.files.get("profile_picture")
        if uploaded and uploaded.filename:
            filename = secure_filename(uploaded.filename)
            extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if extension not in ALLOWED_PROFILE_IMAGE_EXTENSIONS or uploaded.mimetype not in {"image/jpeg", "image/png", "image/webp"}:
                flash("Choose a JPG, PNG, or WEBP image under 5 MB.", "error")
                return redirect(url_for("auth.profile"))
            upload_dir = Path(current_app.static_folder) / "uploads" / "profile_photos"
            upload_dir.mkdir(parents=True, exist_ok=True)
            stored_name = f"user_{current_user.id}_{uuid4().hex}.{extension}"
            uploaded.save(upload_dir / stored_name)
            current_user.profile_picture_url = f"uploads/profile_photos/{stored_name}"
        current_user.portfolio_url = form.portfolio_url.data.strip()
        current_user.certificate_url = form.certificate_url.data.strip()
        if current_user.learner:
            current_user.learner.learning_goals = form.learning_goals.data.strip()
        db.session.commit()
        flash("Your profile was updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", form=form, active_nav="profile")
