from datetime import datetime
from flask import Blueprint, render_template
from flask_login import current_user, login_required
from app.models import Session, Tutor, User, UserSkill

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
@login_required
def index():
    upcoming = Session.query.filter(
        ((Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)),
        Session.scheduled_at >= datetime.utcnow(), Session.status == "confirmed"
    ).order_by(Session.scheduled_at).limit(5).all()
    wanted_ids = [u.skill_id for u in current_user.user_skills if u.type == "wanted"]
    matches = []
    if wanted_ids:
        matches = (
            User.query.join(UserSkill).join(Tutor, Tutor.user_id == User.id)
            .filter(
                UserSkill.skill_id.in_(wanted_ids),
                UserSkill.type == "offering",
                User.id != current_user.id,
                User.is_active.is_(True),
                Tutor.approved_by_admin.is_(True),
            )
            .distinct()
            .order_by(Tutor.avg_rating.desc(), Tutor.response_rate.desc())
            .limit(5)
            .all()
        )
    else:
        matches = []
    offered_ids = {item.skill_id for item in current_user.user_skills if item.type == "offering"}
    wanted_ids = set(wanted_ids)
    barter_matches = []
    if offered_ids and wanted_ids:
        candidates = (
            User.query.join(Tutor, Tutor.user_id == User.id)
            .filter(User.id != current_user.id, User.is_active.is_(True), Tutor.approved_by_admin.is_(True))
            .all()
        )
        for candidate in candidates:
            candidate_offers = {item.skill_id for item in candidate.user_skills if item.type == "offering"}
            candidate_wants = {item.skill_id for item in candidate.user_skills if item.type == "wanted"}
            if wanted_ids & candidate_offers and offered_ids & candidate_wants:
                barter_matches.append(candidate)
    return render_template(
        "dashboard/index.html", active_nav="dashboard", upcoming=upcoming,
        matches=matches, barter_matches=barter_matches[:5]
    )
