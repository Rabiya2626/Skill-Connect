from datetime import datetime, timedelta

from flask import Blueprint, render_template

from app.models import Session, Skill, User

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
    return render_template(
        "main/index.html",
        active_students=User.query.filter_by(is_active=True).count(),
        skills_listed=Skill.query.count(),
        sessions_this_week=Session.query.filter(Session.scheduled_at >= week_start).count(),
    )
