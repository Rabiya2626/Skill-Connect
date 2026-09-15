from datetime import datetime, timedelta
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.booking.routes import _normalize_slot_value, open_slots, overlaps_existing_session
from app.models import Feedback, Notification, Rating, RescheduleRequest, Session, Tutor
from app.sessions.forms import FeedbackForm

sessions_bp = Blueprint("sessions", __name__)

@sessions_bp.route("/sessions")
@login_required
def index():
    now = datetime.utcnow()
    rows = Session.query.filter((Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)).order_by(Session.scheduled_at.desc()).all()
    slots = {
        row.id: [value for value, _ in open_slots(row.tutor.tutor, duration=row.duration_minutes)][:12]
        for row in rows if row.status == "confirmed"
    }
    pending_reschedules = RescheduleRequest.query.join(Session).filter(
        RescheduleRequest.status == "pending",
        ((Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)),
        RescheduleRequest.requested_by_id != current_user.id,
    ).all()
    return render_template("sessions/index.html", active_nav="sessions", sessions=rows, reschedule_slots=slots, pending_reschedules=pending_reschedules, now=now)


@sessions_bp.route("/exchanges")
@login_required
def exchanges():
    if current_user.role != "both":
        abort(403)
    """Expose the existing barter-session workflow without duplicating its data."""
    rows = Session.query.filter(
        Session.is_skill_exchange.is_(True),
        (Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id),
    ).order_by(Session.scheduled_at.desc()).all()
    return render_template("sessions/exchanges.html", active_nav="exchanges", exchanges=rows)

@sessions_bp.route("/session/<int:session_id>/meet")
@login_required
def meet(session_id):
    session = Session.query.filter_by(id=session_id).filter((Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)).first_or_404()
    if session.meeting_closed_at or session.status == "completed":
        flash("This session has ended and can no longer be rejoined.", "warning")
        return redirect(url_for("sessions.index"))
    if session.status != "confirmed":
        flash("This session must be accepted before the meeting room is available.", "warning")
        return redirect(url_for("sessions.index"))
    if session.format != "online":
        flash("This is an in-person session, so it has no video room.", "warning")
        return redirect(url_for("sessions.index"))
    now = datetime.utcnow()
    if session.scheduled_at.date() != now.date() or now < session.scheduled_at:
        flash(
            f"Your session starts at {session.scheduled_at.strftime('%I:%M %p')} on "
            f"{session.scheduled_at.strftime('%d %B %Y')}. You can join when the session begins.",
            "warning",
        )
        return redirect(url_for("sessions.index"))
    return render_template("sessions/meet.html", active_nav="sessions", session=session)


def _meeting_session(session_id):
    return Session.query.filter_by(id=session_id).filter(
        (Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)
    ).first_or_404()


def _meeting_error(message, status_code):
    return jsonify({"ok": False, "message": message}), status_code


@sessions_bp.post("/sessions/<int:session_id>/meeting/join")
@login_required
def meeting_join(session_id):
    session = _meeting_session(session_id)
    now = datetime.utcnow()
    if session.meeting_closed_at or session.status == "completed":
        return _meeting_error("This session has ended and can no longer be rejoined.", 409)
    if session.status != "confirmed":
        return _meeting_error("This session is not available to join.", 409)
    if session.format != "online":
        return _meeting_error("This is an in-person session and has no video room.", 409)
    if session.scheduled_at.date() != now.date() or now < session.scheduled_at:
        return _meeting_error(
            f"Your session starts at {session.scheduled_at.strftime('%I:%M %p')} on "
            f"{session.scheduled_at.strftime('%d %B %Y')}. You can join when the session begins.",
            403,
        )

    is_tutor = current_user.id == session.tutor_id
    joined_attr = "tutor_joined_at" if is_tutor else "learner_joined_at"
    left_attr = "tutor_left_at" if is_tutor else "learner_left_at"
    other_joined_attr = "learner_joined_at" if is_tutor else "tutor_joined_at"
    other_left_attr = "learner_left_at" if is_tutor else "tutor_left_at"
    had_left = getattr(session, left_attr) is not None
    setattr(session, joined_attr, now)
    setattr(session, left_attr, None)

    other_is_present = getattr(session, other_joined_attr) is not None and getattr(session, other_left_attr) is None
    if other_is_present and (session.both_joined_at is None or had_left or getattr(session, other_left_attr) is not None):
        session.both_joined_at = now
    db.session.commit()
    return jsonify({"ok": True, "both_joined": session.both_joined_at is not None})


@sessions_bp.post("/sessions/<int:session_id>/meeting/leave")
@login_required
def meeting_leave(session_id):
    session = _meeting_session(session_id)
    if session.status not in {"confirmed", "completed"}:
        return _meeting_error("This session is not active.", 409)
    if session.meeting_closed_at:
        return jsonify({"ok": True, "closed": True})

    now = datetime.utcnow()
    is_tutor = current_user.id == session.tutor_id
    joined_attr = "tutor_joined_at" if is_tutor else "learner_joined_at"
    left_attr = "tutor_left_at" if is_tutor else "learner_left_at"
    other_left_attr = "learner_left_at" if is_tutor else "tutor_left_at"
    if getattr(session, joined_attr) is None:
        return jsonify({"ok": True, "closed": False})
    setattr(session, left_attr, now)

    other_has_left = getattr(session, other_left_attr) is not None
    if session.both_joined_at is not None and other_has_left:
        joint_end = min(now, getattr(session, other_left_attr))
        if joint_end - session.both_joined_at >= timedelta(minutes=5):
            session.meeting_closed_at = now
            session.status = "completed"
    db.session.commit()
    return jsonify({"ok": True, "closed": session.meeting_closed_at is not None})


@sessions_bp.post("/sessions/<int:session_id>/respond/<decision>")
@login_required
def respond_to_booking(session_id, decision):
    if decision not in {"accept", "reject"}:
        abort(404)
    session = Session.query.filter_by(id=session_id, tutor_id=current_user.id).first_or_404()
    if session.status != "pending":
        flash("This booking request has already been handled.", "warning")
        return redirect(url_for("sessions.index"))

    if decision == "accept":
        if overlaps_existing_session(session.tutor_id, session.scheduled_at, session.duration_minutes, session.id):
            flash("That time slot is no longer available.", "error")
            return redirect(url_for("sessions.index"))
        session.status = "confirmed"
        message = f"{current_user.name} accepted your {session.skill.name} session."
        notification_type = "booking_accepted"
        flash("Session accepted. Both of you can now join the video room.", "success")
    else:
        session.status = "cancelled"
        message = f"{current_user.name} declined your {session.skill.name} session request."
        notification_type = "booking_rejected"
        flash("Session request declined.", "success")
    db.session.add(Notification(user_id=session.learner_id, type=notification_type, message=message, session_id=session.id))
    db.session.commit()
    return redirect(url_for("sessions.index"))

@sessions_bp.post("/sessions/<int:session_id>/cancel")
@login_required
def cancel(session_id):
    session = Session.query.filter_by(id=session_id).filter((Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)).first_or_404()
    if session.status == "confirmed":
        session.status = "cancelled"; db.session.add(Notification(user_id=session.tutor_id if session.learner_id == current_user.id else session.learner_id, type="session_cancelled", message="A scheduled session was cancelled.")); db.session.commit(); flash("Session cancelled.", "success")
    return redirect(url_for("sessions.index"))

@sessions_bp.post("/sessions/<int:session_id>/reschedule")
@login_required
def request_reschedule(session_id):
    session = Session.query.filter_by(id=session_id, status="confirmed").filter((Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)).first_or_404()
    proposed_at = _normalize_slot_value(request.form.get("proposed_at"))
    if not proposed_at or not any(slot[0] == proposed_at for slot in open_slots(session.tutor.tutor, duration=session.duration_minutes)):
        flash("Choose an available future slot.", "error")
        return redirect(url_for("sessions.index"))
    RescheduleRequest.query.filter_by(session_id=session.id, status="pending").update({"status": "declined"})
    db.session.add(RescheduleRequest(session_id=session.id, requested_by_id=current_user.id, proposed_at=proposed_at))
    other_user_id = session.learner_id if session.tutor_id == current_user.id else session.tutor_id
    db.session.add(Notification(user_id=other_user_id, type="reschedule_request", message=f"{current_user.name} proposed a new time for your {session.skill.name} session.", session_id=session.id))
    db.session.commit()
    flash("Reschedule request sent.", "success")
    return redirect(url_for("sessions.index"))

@sessions_bp.post("/reschedule-requests/<int:request_id>/<decision>")
@login_required
def respond_to_reschedule(request_id, decision):
    if decision not in {"accept", "decline"}:
        abort(404)
    change = RescheduleRequest.query.filter_by(id=request_id, status="pending").first_or_404()
    session = change.session
    if current_user.id not in {session.tutor_id, session.learner_id} or current_user.id == change.requested_by_id:
        abort(403)
    if decision == "accept":
        if overlaps_existing_session(session.tutor_id, change.proposed_at, session.duration_minutes, session.id):
            flash("That proposed time is no longer available.", "error")
            return redirect(url_for("sessions.index"))
        session.scheduled_at = change.proposed_at
        change.status = "accepted"
        message = f"{current_user.name} accepted the new session time."
    else:
        change.status = "declined"
        message = f"{current_user.name} declined the proposed session time."
    db.session.add(Notification(user_id=change.requested_by_id, type=f"reschedule_{decision}ed", message=message, session_id=session.id))
    db.session.commit()
    return redirect(url_for("sessions.index"))

@sessions_bp.route("/sessions/<int:session_id>/feedback", methods=["GET", "POST"])
@login_required
def feedback(session_id):
    session = Session.query.filter_by(id=session_id, status="completed").filter((Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)).first_or_404()
    recipient_id = session.learner_id if session.tutor_id == current_user.id else session.tutor_id
    form = FeedbackForm()
    if form.validate_on_submit():
        rating = Rating.query.filter_by(session_id=session.id, rated_user_id=recipient_id).first()
        if not rating:
            db.session.add(Rating(session_id=session.id, rated_user_id=recipient_id, rating_value=form.rating_value.data))
        if form.comment.data.strip():
            db.session.add(Feedback(session_id=session.id, from_user_id=current_user.id, to_user_id=recipient_id, comment=form.comment.data.strip()))
        tutor = db.session.get(Tutor, recipient_id)
        if tutor:
            values = [row.rating_value for row in Rating.query.join(Session).filter(Session.tutor_id == recipient_id).all()]
            tutor.avg_rating = sum(values) / len(values) if values else 0
        db.session.add(Notification(user_id=recipient_id, type="feedback", message=f"{current_user.name} left feedback for your session."))
        db.session.commit(); flash("Thank you for your feedback.", "success")
        return redirect(url_for("sessions.index"))
    return render_template("sessions/feedback.html", active_nav="sessions", form=form, session=session)
