from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Session, Skill, Tutor, User

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
    tab = request.args.get("tab", "overview")
    query = request.args.get("q", "")
    users = User.query
    if query: users = users.filter((User.name.ilike(f"%{query}%")) | (User.email.ilike(f"%{query}%")))
    return render_template("admin/index.html", active_nav="admin", tab=tab, users=users.order_by(User.created_at.desc()).all(), pending=Tutor.query.filter_by(approved_by_admin=False).all(), skills=Skill.query.order_by(Skill.name).all(), stats={"users": User.query.filter_by(is_active=True).count(), "skills": Skill.query.count(), "sessions": Session.query.count(), "pending": Tutor.query.filter_by(approved_by_admin=False).count()})

@admin_bp.post("/admin/tutors/<int:user_id>/<action>")
@admin_required
def approve_tutor(user_id, action):
    tutor = Tutor.query.get_or_404(user_id); tutor.approved_by_admin = action == "approve"; db.session.commit(); flash("Tutor approval updated.", "success")
    return redirect(url_for("admin.index", tab="approvals"))

@admin_bp.post("/admin/users/<int:user_id>/deactivate")
@admin_required
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id: user.is_active = False; db.session.commit(); flash("Account deactivated.", "success")
    return redirect(url_for("admin.index", tab="users"))

@admin_bp.post("/admin/skills")
@admin_required
def add_skill():
    db.session.add(Skill(name=request.form["name"].strip(), category=request.form["category"].strip(), description=request.form.get("description", ""))); db.session.commit(); flash("Skill added.", "success")
    return redirect(url_for("admin.index", tab="skills"))

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
    return redirect(url_for("admin.index", tab="users"))
