from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from datetime import datetime

from app.models import Notification, Report, Session, Skill, Tutor, User

admin_bp = Blueprint("admin", __name__)

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin": abort(403)
        return view(*args, **kwargs)
    return wrapped

@admin_bp.route("/admin")
@admin_required
def index():
    query = request.args.get("q", "")
    report_status = request.args.get("report_status", "")
    report_severity = request.args.get("report_severity", "")
    users = User.query
    if query: users = users.filter((User.name.ilike(f"%{query}%")) | (User.email.ilike(f"%{query}%")))
    reports = Report.query
    if report_status in {"open", "in_review", "resolved", "dismissed"}:
        reports = reports.filter_by(status=report_status)
    if report_severity in {"low", "medium", "high"}:
        reports = reports.filter_by(severity=report_severity)
    stats = {"users": User.query.count(), "tutors": Tutor.query.count(), "learners": User.query.filter(User.role.in_(("learner", "both"))).count(), "sessions": Session.query.count(), "completed": Session.query.filter_by(status="completed").count(), "skills": Skill.query.count(), "reports": Report.query.filter(Report.status.in_(("open", "in_review"))).count()}
    return render_template("admin/index.html", active_nav="admin", users=users.order_by(User.created_at.desc()).all(), skills=Skill.query.order_by(Skill.name).all(), reports=reports.order_by(Report.created_at.desc()).all(), stats=stats, selected_reports={"status": report_status, "severity": report_severity})

@admin_bp.post("/admin/users/<int:user_id>/deactivate")
@admin_required
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id: user.is_active = False; db.session.commit(); flash("Account deactivated.", "success")
    return redirect(url_for("admin.index") + "#users")

@admin_bp.post("/admin/skills")
@admin_required
def add_skill():
    db.session.add(Skill(name=request.form["name"].strip(), category=request.form["category"].strip(), description=request.form.get("description", ""))); db.session.commit(); flash("Skill added.", "success")
    return redirect(url_for("admin.index") + "#skills")

@admin_bp.post("/admin/users/<int:user_id>/skills/<int:skill_id>/<skill_type>/verify")
@admin_required
def verify_user_skill(user_id, skill_id, skill_type):
    if skill_type not in {"offering", "wanted"}:
        abort(404)
    from app.models import UserSkill
    link = UserSkill.query.filter_by(user_id=user_id, skill_id=skill_id, type=skill_type).first_or_404()
    link.is_verified = True
    db.session.commit()
    flash("Skill verification badge awarded.", "success")
    return redirect(url_for("admin.index") + "#users")


@admin_bp.post("/admin/reports/<int:report_id>")
@admin_required
def update_report(report_id):
    report = Report.query.get_or_404(report_id)
    status = request.form.get("status")
    if status not in {"open", "in_review", "resolved", "dismissed"}:
        abort(400)
    report.status = status
    report.resolved_at = datetime.utcnow() if status in {"resolved", "dismissed"} else None
    db.session.commit()
    flash("Report status updated.", "success")
    return redirect(url_for("admin.index") + "#reports")
