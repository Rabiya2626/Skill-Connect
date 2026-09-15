from datetime import datetime
from flask import Blueprint, render_template
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Feedback, Notification, Session, Tutor, User, UserSkill

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
        candidate_ids = (
            db.session.query(User.id.label("user_id"))
            .join(UserSkill).join(Tutor, Tutor.user_id == User.id)
            .filter(
                UserSkill.skill_id.in_(wanted_ids),
                UserSkill.type == "offering",
                User.id != current_user.id,
                User.is_active.is_(True),
            )
            .group_by(User.id)
            .order_by(db.func.max(Tutor.avg_rating).desc(), db.func.max(Tutor.response_rate).desc())
            .limit(5)
            .subquery()
        )
        matches = User.query.join(candidate_ids, candidate_ids.c.user_id == User.id).all()
    else:
        matches = []
    barter_matches = []
    if current_user.role == "both":
        offered_ids = {item.skill_id for item in current_user.user_skills if item.type == "offering"}
        wanted_ids = set(wanted_ids)
    else:
        offered_ids = set()
        wanted_ids = set()
    if current_user.role == "both" and offered_ids and wanted_ids:
        candidates = (
            User.query.join(Tutor, Tutor.user_id == User.id)
            .filter(User.id != current_user.id, User.is_active.is_(True))
            .all()
        )
        for candidate in candidates:
            candidate_offers = {item.skill_id for item in candidate.user_skills if item.type == "offering"}
            candidate_wants = {item.skill_id for item in candidate.user_skills if item.type == "wanted"}
            if wanted_ids & candidate_offers and offered_ids & candidate_wants:
                barter_matches.append(candidate)
    all_sessions = Session.query.filter(
        (Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)
    )
    learning_skills = {row.skill_id: row.skill for row in all_sessions.filter_by(learner_id=current_user.id).all()}
    completed_learning_ids = {
        row.skill_id for row in all_sessions.filter_by(learner_id=current_user.id, status="completed").all()
    }
    activity = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).limit(5).all()
    stats = {
        "upcoming": len(upcoming),
        "learning": len([item for item in current_user.user_skills if item.type == "wanted"]),
        "teaching": len([item for item in current_user.user_skills if item.type == "offering"]),
        "completed": all_sessions.filter_by(status="completed").count(),
    }
    return render_template(
        "dashboard/index.html", active_nav="dashboard", upcoming=upcoming,
        matches=matches, barter_matches=barter_matches[:5], stats=stats,
        learning_progress=[{"skill": skill, "percent": 100 if skill_id in completed_learning_ids else 35}
                           for skill_id, skill in learning_skills.items()], activity=activity,
    )
