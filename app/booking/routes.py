from datetime import datetime, time, timedelta
from secrets import token_urlsafe
from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError
from app.extensions import csrf, db
from app.models import Notification, Session, Skill, Tutor, User, UserSkill

booking_bp = Blueprint("booking", __name__)


def _normalize_slot_value(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


BOOKING_DURATIONS = (30, 60, 90)


def overlaps_existing_session(tutor_id, scheduled_at, duration, exclude_session_id=None):
    """Return whether a proposed interval overlaps a pending or confirmed session."""
    candidates = Session.query.filter(
        Session.tutor_id == tutor_id,
        Session.status.in_(("pending", "confirmed")),
    )
    if exclude_session_id is not None:
        candidates = candidates.filter(Session.id != exclude_session_id)
    proposed_end = scheduled_at + timedelta(minutes=duration)
    return any(
        scheduled_at < item.scheduled_at + timedelta(minutes=item.duration_minutes)
        and proposed_end > item.scheduled_at
        for item in candidates
    )


def open_slots(tutor, days=14, duration=60):
    now = datetime.utcnow(); slots = []
    # Until a tutor publishes their own hours, let learners request a weekday
    # slot. The tutor still has to explicitly accept every request.
    availability_windows = [
        (item.day_of_week, item.start_time, item.end_time, item.format)
        for item in tutor.availability
    ] or [(day, time(9), time(17), "either") for day in range(5)]
    for offset in range(days):
        date = (now + timedelta(days=offset)).date()
        for day_of_week, start_time, end_time, slot_format in availability_windows:
            if day_of_week != date.weekday(): continue
            current = datetime.combine(date, start_time)
            end = datetime.combine(date, end_time)
            while current + timedelta(minutes=duration) <= end:
                if current > now and not overlaps_existing_session(tutor.user_id, current, duration):
                    slots.append((current, slot_format))
                current += timedelta(minutes=duration)
    return slots


def group_slots_by_date(slots):
    groups = {}
    for scheduled_at, slot_format in slots:
        key = scheduled_at.date().isoformat()
        if key not in groups:
            groups[key] = {
                "key": key,
                "weekday": scheduled_at.strftime("%a"),
                "day": scheduled_at.strftime("%d"),
                "month": scheduled_at.strftime("%b"),
                "full_date": scheduled_at.strftime("%A, %d %B"),
                "slots": [],
            }
        groups[key]["slots"].append({"value": scheduled_at.isoformat(), "time": scheduled_at.strftime("%H:%M"), "format": slot_format})
    return list(groups.values())

@booking_bp.errorhandler(CSRFError)
def handle_csrf_error(error):
    flash("Your session expired. Please try the booking again.", "error")
    tutor_id = request.view_args.get("tutor_id")
    if tutor_id is not None:
        return redirect(url_for("booking.book", tutor_id=tutor_id))
    return redirect(url_for("dashboard.index"))


@booking_bp.route("/book/<int:tutor_id>", methods=["GET", "POST"])
@login_required
def book(tutor_id):
    tutor = Tutor.query.filter_by(user_id=tutor_id).first()
    if tutor is None:
        tutor = Tutor(user_id=tutor_id, avg_rating=0, session_count=0, response_rate=0)
    user = tutor.user or db.session.get(User, tutor_id)
    if user is None or tutor_id == current_user.id or not user.is_active:
        return redirect(url_for("dashboard.index"))
    tutor.user = user
    skills = [u.skill for u in user.user_skills if u.type == "offering"]
    exchange_skills = [u.skill for u in current_user.user_skills if u.type == "offering"] if current_user.role == "both" else []
    if request.method == "POST":
        scheduled_at_raw = request.form.get("scheduled_at")
        skill_id_raw = request.form.get("skill_id")
        duration_raw = request.form.get("duration_minutes", 60)
        if not scheduled_at_raw:
            flash("Please select a time slot.", "error")
            return redirect(url_for("booking.book", tutor_id=tutor_id))
        try:
            scheduled_at = _normalize_slot_value(scheduled_at_raw)
            duration = int(duration_raw)
            skill_id = int(skill_id_raw)
        except (TypeError, ValueError):
            flash("Please choose a valid skill, time, and duration.", "error")
            return redirect(url_for("booking.book", tutor_id=tutor_id))
        if duration not in BOOKING_DURATIONS:
            flash("Choose a supported session duration.", "error")
            return redirect(url_for("booking.book", tutor_id=tutor_id))
        available_slots = open_slots(tutor, duration=duration)
        if scheduled_at is None or not any(_normalize_slot_value(slot[0]) == scheduled_at for slot in available_slots):
            flash("That slot is no longer available. Please choose another.", "error")
            return redirect(url_for("booking.book", tutor_id=tutor_id))
        skill = db.session.get(Skill, skill_id)
        if skill is None or not UserSkill.query.filter_by(user_id=tutor_id, skill_id=skill_id, type="offering").first():
            flash("Please choose a valid skill.", "error")
            return redirect(url_for("booking.book", tutor_id=tutor_id))
        booking_mode = request.form.get("booking_mode", "paid")
        if booking_mode not in {"paid", "exchange"}:
            flash("Choose a valid booking mode.", "error")
            return redirect(url_for("booking.book", tutor_id=tutor_id))
        is_skill_exchange = booking_mode == "exchange"
        exchange_skill_id = request.form.get("exchange_skill_id", type=int)
        if is_skill_exchange:
            if current_user.role != "both":
                flash("Skill exchanges are available only for users who teach and learn.", "error")
                return redirect(url_for("booking.book", tutor_id=tutor_id))
            exchange_link = UserSkill.query.filter_by(
                user_id=current_user.id, skill_id=exchange_skill_id, type="offering"
            ).first()
            if not exchange_link:
                flash("Choose one of your offered skills for the exchange.", "error")
                return redirect(url_for("booking.book", tutor_id=tutor_id))
        session = Session(
            tutor_id=tutor_id,
            learner_id=current_user.id,
            skill_id=skill.id,
            scheduled_at=scheduled_at,
            duration_minutes=duration,
            format=request.form.get("format", "online"),
            is_skill_exchange=is_skill_exchange,
            exchange_skill_id=exchange_skill_id if is_skill_exchange else None,
            status="pending",
        )
        db.session.add(session)
        db.session.flush()
        session.meeting_url = f"https://{current_app.config['JITSI_DOMAIN']}/skillconnect-{session.id}-{token_urlsafe(8)}"
        tutor_message = f"{current_user.name} requested a {skill.name} session on {scheduled_at.strftime('%d %b %H:%M')}. Please accept or reject it."
        learner_message = f"Your {skill.name} session request with {user.name} was sent and is awaiting their response."
        db.session.add(Notification(user_id=tutor_id, type="booking_request", message=tutor_message, session_id=session.id))
        db.session.add(Notification(user_id=current_user.id, type="booking_pending", message=learner_message, session_id=session.id))
        db.session.commit()
        return render_template("booking/confirmation.html", active_nav="sessions", session=session, tutor=tutor)
    if not tutor.availability:
        flash("Suggested weekday slot request hours are 09:00–17:00; the tutor confirms every request.", "warning")
    return render_template(
        "booking/book.html",
        active_nav="sessions",
        tutor=tutor,
        skills=skills,
        exchange_skills=exchange_skills,
        slot_groups_by_duration={duration: group_slots_by_date(open_slots(tutor, duration=duration)) for duration in BOOKING_DURATIONS},
        durations=BOOKING_DURATIONS,
        using_default_availability=not tutor.availability,
    )


@booking_bp.route("/sessions/<int:session_id>/calendar")
@login_required
def calendar(session_id):
    session = Session.query.filter_by(id=session_id).filter(
        (Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)
    ).first_or_404()
    start = session.scheduled_at.strftime("%Y%m%dT%H%M%S")
    end = (session.scheduled_at + timedelta(minutes=session.duration_minutes)).strftime("%Y%m%dT%H%M%S")
    title = f"SkillConnect: {session.skill.name} with {session.tutor.name}"
    location = session.meeting_url if session.format == "online" else "In person"
    ics = "\r\n".join(("BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SkillConnect//EN", "BEGIN:VEVENT", f"UID:skillconnect-{session.id}@skillconnect", f"DTSTART:{start}", f"DTEND:{end}", f"SUMMARY:{title}", f"LOCATION:{location}", f"DESCRIPTION:Session reference SC-{session.id:06d}", "END:VEVENT", "END:VCALENDAR", ""))
    return Response(ics, mimetype="text/calendar", headers={"Content-Disposition": f'attachment; filename="skillconnect-SC-{session.id:06d}.ics"'})
