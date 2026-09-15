from flask import Flask
from flask_login import current_user

from app.config import DevelopmentConfig
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_object=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.booking.routes import booking_bp
    from app.dashboard.routes import dashboard_bp
    from app.main.routes import main_bp
    from app.messages.routes import messages_bp
    from app.notifications.routes import notifications_bp
    from app.payments.routes import payments_bp
    from app.sessions.routes import sessions_bp
    from app.skills.routes import skills_bp
    from app.tutors.routes import tutors_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(skills_bp)
    app.register_blueprint(tutors_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_navigation_counts():
        if not current_user.is_authenticated:
            return {"unread_notification_count": 0, "unread_message_count": 0, "session_action_count": 0}
        from app.models import Message, Notification, Session

        return {
            "unread_notification_count": Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count(),
            "unread_message_count": Message.query.join(Session).filter(
                Message.is_read.is_(False),
                Message.sender_id != current_user.id,
                (Session.tutor_id == current_user.id) | (Session.learner_id == current_user.id),
            ).count(),
            "session_action_count": Session.query.filter(
                Session.tutor_id == current_user.id,
                Session.status == "pending",
            ).count(),
        }

    return app
