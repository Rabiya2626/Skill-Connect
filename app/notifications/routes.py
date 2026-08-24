from flask import Blueprint, render_template
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Notification

notifications_bp = Blueprint("notifications", __name__)

@notifications_bp.route("/notifications")
@login_required
def index():
    rows = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    for row in rows: row.is_read = True
    db.session.commit()
    return render_template("notifications/index.html", active_nav="notifications", notifications=rows)
