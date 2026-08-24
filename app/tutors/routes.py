from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Feedback, Session, Tutor, User

tutors_bp = Blueprint("tutors", __name__)


@tutors_bp.route("/tutor/<int:user_id>")
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    tutor = Tutor.query.filter_by(user_id=user_id).first()
    if tutor is None:
        tutor = Tutor(user_id=user_id, approved_by_admin=False, avg_rating=0, session_count=0, response_rate=0)
    reviews = Feedback.query.join(Session, Feedback.session_id == Session.id).filter(Session.tutor_id == user_id).order_by(Feedback.created_at.desc()).limit(6).all()
    return render_template("tutors/profile.html", active_nav="browse", tutor=tutor, reviews=reviews, user=user)
