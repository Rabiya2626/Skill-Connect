from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.messages import messages_bp
from app.models import Message, Notification, Session


@messages_bp.route("/messages")
@login_required
def index():
    sessions = Session.query.filter(
        (Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)
    ).order_by(Session.updated_at.desc()).all()
    conversations = []
    for session in sessions:
        latest = Message.query.filter_by(session_id=session.id).order_by(Message.created_at.desc()).first()
        if latest:
            other = session.learner if session.tutor_id == current_user.id else session.tutor
            unread = Message.query.filter_by(session_id=session.id, is_read=False).filter(Message.sender_id != current_user.id).count()
            conversations.append({"session": session, "other": other, "latest": latest, "unread": unread})
    return render_template("messages/index.html", active_nav="messages", conversations=conversations)


@messages_bp.route("/sessions/<int:session_id>/messages", methods=["GET", "POST"])
@login_required
def thread(session_id):
    session = Session.query.filter_by(id=session_id).filter((Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id)).first_or_404()
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body or len(body) > 2000:
            flash("Messages must be between 1 and 2,000 characters.", "error")
        else:
            recipient_id = session.learner_id if current_user.id == session.tutor_id else session.tutor_id
            db.session.add(Message(session_id=session.id, sender_id=current_user.id, body=body))
            db.session.add(Notification(user_id=recipient_id, type="message", message=f"{current_user.name} sent you a message about {session.skill.name}.", session_id=session.id))
            db.session.commit()
            return redirect(url_for("messages.thread", session_id=session.id))
    messages = Message.query.filter_by(session_id=session.id).order_by(Message.created_at).all()
    for message in messages:
        if message.sender_id != current_user.id:
            message.is_read = True
    db.session.commit()
    return render_template("messages/thread.html", active_nav="sessions", session=session, messages=messages)
