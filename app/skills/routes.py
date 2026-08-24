from datetime import time

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Skill, Tutor, TutorAvailability, User, UserSkill

skills_bp = Blueprint("skills", __name__)
LEVELS = {"Beginner", "Intermediate", "Advanced"}

@skills_bp.route("/browse")
@login_required
def browse():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    minimum_rating = request.args.get("minimum_rating", type=float)
    availability_format = request.args.get("format", "")
    sort = request.args.get("sort", "recommended")
    query = (
        User.query.join(UserSkill)
        .join(Skill)
        .join(Tutor, Tutor.user_id == User.id)
        .filter(
            UserSkill.type == "offering",
            User.is_active.is_(True),
            Tutor.approved_by_admin.is_(True),
            User.id != current_user.id,
        )
    )
    if q:
        query = query.filter((User.name.ilike(f"%{q}%")) | (Skill.name.ilike(f"%{q}%")))
    if category:
        query = query.filter(Skill.category == category)
    if minimum_rating is not None:
        query = query.filter(Tutor.avg_rating >= minimum_rating)
    if availability_format in {"online", "in_person"}:
        query = query.join(TutorAvailability).filter(
            TutorAvailability.format.in_((availability_format, "either"))
        )
    if sort == "rating":
        query = query.order_by(Tutor.avg_rating.desc(), Tutor.session_count.desc())
    elif sort == "response":
        query = query.order_by(Tutor.response_rate.desc(), Tutor.avg_rating.desc())
    else:
        wanted_ids = [item.skill_id for item in current_user.user_skills if item.type == "wanted"]
        if wanted_ids:
            query = query.order_by(db.case((UserSkill.skill_id.in_(wanted_ids), 1), else_=0).desc(), Tutor.avg_rating.desc())
        else:
            query = query.order_by(Tutor.avg_rating.desc(), Tutor.session_count.desc())
    tutors = query.distinct().all()
    return render_template(
        "skills/browse.html",
        active_nav="browse",
        tutors=tutors,
        categories=[s[0] for s in db.session.query(Skill.category).distinct().all()],
        selected={"q": q, "category": category, "minimum_rating": minimum_rating, "format": availability_format, "sort": sort},
    )

@skills_bp.route("/my-skills", methods=["GET", "POST"])
@login_required
def my_skills():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        skill_type = request.form.get("type")
        level = request.form.get("proficiency_level")
        if not name or skill_type not in {"offering", "wanted"} or level not in LEVELS:
            flash("Choose a skill, type, and valid proficiency level.", "error")
            return redirect(url_for("skills.my_skills"))
        skill = Skill.query.filter(db.func.lower(Skill.name) == name.lower()).first()
        if not skill:
            skill = Skill(name=name, category=request.form.get("category", "").strip() or "Other")
            db.session.add(skill); db.session.flush()
        link = UserSkill.query.filter_by(user_id=current_user.id, skill_id=skill.id, type=skill_type).first()
        if not link:
            db.session.add(UserSkill(user_id=current_user.id, skill_id=skill.id, type=skill_type, proficiency_level=level))
            db.session.commit(); flash("Skill added.", "success")
        return redirect(url_for("skills.my_skills"))
    availability = []
    if current_user.tutor:
        availability = current_user.tutor.availability
    return render_template("skills/my_skills.html", active_nav="my_skills", availability=availability)

@skills_bp.post("/my-skills/<int:skill_id>/<skill_type>/delete")
@login_required
def delete_my_skill(skill_id, skill_type):
    link = UserSkill.query.filter_by(user_id=current_user.id, skill_id=skill_id, type=skill_type).first_or_404()
    db.session.delete(link); db.session.commit(); flash("Skill removed.", "success")
    return redirect(url_for("skills.my_skills"))


@skills_bp.post("/my-availability")
@login_required
def add_availability():
    if not current_user.tutor:
        flash("Choose a tutor or both profile to publish availability.", "error")
        return redirect(url_for("skills.my_skills"))
    try:
        days = {int(value) for value in request.form.getlist("days")}
        start_time = time.fromisoformat(request.form["start_time"])
        end_time = time.fromisoformat(request.form["end_time"])
    except (KeyError, TypeError, ValueError):
        flash("Choose a valid day and time range.", "error")
        return redirect(url_for("skills.my_skills"))
    if not days or not days.issubset(range(7)) or start_time >= end_time:
        flash("Select one or more weekdays and an end time after the start time.", "error")
        return redirect(url_for("skills.my_skills"))
    existing_days = {
        item.day_of_week
        for item in current_user.tutor.availability
        if item.start_time == start_time and item.end_time == end_time
    }
    for day_of_week in days - existing_days:
        db.session.add(
            TutorAvailability(
                tutor_id=current_user.id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                format=request.form.get("format", "either"),
            )
        )
    db.session.commit()
    flash("Availability published. Learners can now request these time slots.", "success")
    return redirect(url_for("skills.my_skills"))


@skills_bp.post("/my-availability/<int:availability_id>/delete")
@login_required
def delete_availability(availability_id):
    availability = TutorAvailability.query.filter_by(
        id=availability_id, tutor_id=current_user.id
    ).first_or_404()
    db.session.delete(availability)
    db.session.commit()
    flash("Availability removed.", "success")
    return redirect(url_for("skills.my_skills"))
