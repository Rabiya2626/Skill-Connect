"""Scheduled-job hook for a cron runner.

Invoke `create_session_reminders()` hourly from Celery, APScheduler, or a
platform scheduler. It creates one reminder notification per confirmed
session that starts in the next 24 hours.
"""
from datetime import datetime, timedelta
from app.extensions import db
from app.models import Notification, Session

def create_session_reminders():
    now, cutoff = datetime.utcnow(), datetime.utcnow() + timedelta(hours=24)
    sessions = Session.query.filter(Session.status == "confirmed", Session.scheduled_at.between(now, cutoff)).all()
    for session in sessions:
        message = f"Reminder: your {session.skill.name} session starts within 24 hours."
        for user_id in (session.tutor_id, session.learner_id):
            if not Notification.query.filter_by(user_id=user_id, type="session_reminder", message=message).first():
                db.session.add(Notification(user_id=user_id, type="session_reminder", message=message))
    db.session.commit()
