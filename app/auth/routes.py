from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.auth.forms import LoginForm, PasswordResetForm, PasswordResetRequestForm, ProfileForm, RegistrationForm
from app.extensions import db
from app.models import Learner, Tutor, User
from app.services.email import send_email

auth_bp = Blueprint("auth", __name__)


def _token_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="skillconnect-account")


def _account_token(user, purpose):
    return _token_serializer().dumps({"user_id": user.id, "purpose": purpose})


def _user_from_token(token, purpose, max_age=3600):
    try:
        payload = _token_serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if payload.get("purpose") != purpose:
        return None
    return db.session.get(User, payload.get("user_id"))


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
        login_user(user)
        verification_url = url_for("auth.verify_email", token=_account_token(user, "verify"), _external=True)
        send_email(user.email, "Verify your SkillConnect email", f"<p>Welcome to SkillConnect.</p><p><a href=\"{verification_url}\">Verify your email</a></p>")
        flash("Your profile is ready. Check your email to verify your account.", "success")
        return redirect(url_for("dashboard.index"))
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
        flash("Incorrect email or password.", "error")
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
            send_email(user.email, "Reset your SkillConnect password", f"<p><a href=\"{reset_url}\">Reset your password</a></p>")
        flash("If that email belongs to an account, a password-reset link has been sent.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = _user_from_token(token, "reset")
    if not user:
        flash("That password-reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset. You can now sign in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if request.method == "GET" and current_user.learner:
        form.learning_goals.data = current_user.learner.learning_goals
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.bio = form.bio.data.strip()
        current_user.profile_picture_url = form.profile_picture_url.data.strip()
        current_user.portfolio_url = form.portfolio_url.data.strip()
        current_user.certificate_url = form.certificate_url.data.strip()
        if current_user.learner:
            current_user.learner.learning_goals = form.learning_goals.data.strip()
        db.session.commit()
        flash("Your profile was updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", form=form, active_nav="profile")
