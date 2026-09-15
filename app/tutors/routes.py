from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Feedback, Rating, Report, Session, Tutor, User

tutors_bp = Blueprint("tutors", __name__)


@tutors_bp.route("/tutor/<int:user_id>")
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    tutor = Tutor.query.filter_by(user_id=user_id).first()
    if tutor is None:
        tutor = Tutor(user_id=user_id, avg_rating=0, session_count=0, response_rate=0)
    reviews = Feedback.query.join(Session, Feedback.session_id == Session.id).filter(Session.tutor_id == user_id).order_by(Feedback.created_at.desc()).limit(6).all()
    rating_values = [row.rating_value for row in Rating.query.join(Session).filter(Session.tutor_id == user_id).all()]
    rating_breakdown = {star: rating_values.count(star) for star in range(5, 0, -1)}
    return render_template("tutors/profile.html", active_nav="browse", tutor=tutor, reviews=reviews, user=user, rating_breakdown=rating_breakdown, rating_count=len(rating_values))


@tutors_bp.post("/tutor/<int:user_id>/report")
@login_required
def report(user_id):
    if user_id == current_user.id:
        flash("You cannot report your own profile.", "error")
        return redirect(url_for("tutors.profile", user_id=user_id))
    User.query.get_or_404(user_id)
    category = request.form.get("category", "other")
    description = request.form.get("description", "").strip()
    severity = request.form.get("severity", "medium")
    if category not in {"inappropriate_behavior", "fake_profile", "scam_fraud", "harassment", "other"} or severity not in {"low", "medium", "high"} or not description:
        flash("Choose a category, severity, and description for the report.", "error")
    else:
        db.session.add(Report(reporter_id=current_user.id, reported_user_id=user_id, category=category, severity=severity, description=description))
        db.session.commit()
        flash("Your report has been sent to the platform moderators.", "success")
    return redirect(url_for("tutors.profile", user_id=user_id))
