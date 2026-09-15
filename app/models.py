from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("learner", "tutor", "both", "admin"), nullable=False, default="learner")
    profile_picture_url = db.Column(db.String(500))
    bio = db.Column(db.Text)
    portfolio_url = db.Column(db.String(500))
    certificate_url = db.Column(db.String(500))
    terms_accepted_at = db.Column(db.DateTime)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    tutor = db.relationship("Tutor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    learner = db.relationship("Learner", back_populates="user", uselist=False, cascade="all, delete-orphan")
    user_skills = db.relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        # PBKDF2 is broadly available on local Python installations (including
        # environments where hashlib does not expose scrypt).
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Skill(TimestampMixin, db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    users = db.relationship("UserSkill", back_populates="skill", cascade="all, delete-orphan")


class UserSkill(TimestampMixin, db.Model):
    __tablename__ = "user_skills"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), primary_key=True)
    type = db.Column(db.Enum("offering", "wanted"), primary_key=True)
    proficiency_level = db.Column(db.String(40), nullable=False)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    user = db.relationship("User", back_populates="user_skills")
    skill = db.relationship("Skill", back_populates="users")


class Tutor(TimestampMixin, db.Model):
    __tablename__ = "tutors"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    avg_rating = db.Column(db.Numeric(3, 2), nullable=False, default=0)
    session_count = db.Column(db.Integer, nullable=False, default=0)
    response_rate = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    user = db.relationship("User", back_populates="tutor")
    availability = db.relationship("TutorAvailability", back_populates="tutor", cascade="all, delete-orphan")


class TutorAvailability(TimestampMixin, db.Model):
    """A recurring weekly time window in the tutor's local campus time zone."""
    __tablename__ = "tutor_availability"
    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutors.user_id"), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # Monday is 0
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    format = db.Column(db.Enum("online", "in_person", "either"), nullable=False, default="either")
    tutor = db.relationship("Tutor", back_populates="availability")


class Learner(TimestampMixin, db.Model):
    __tablename__ = "learners"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    learning_goals = db.Column(db.Text)
    user = db.relationship("User", back_populates="learner")


class TutoringRequest(TimestampMixin, db.Model):
    __tablename__ = "tutoring_requests"
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    status = db.Column(db.Enum("pending", "accepted", "rejected"), nullable=False, default="pending")
    message = db.Column(db.Text)
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Session(TimestampMixin, db.Model):
    __tablename__ = "sessions"
    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    format = db.Column(db.Enum("online", "in_person"), nullable=False, default="online")
    status = db.Column(
        db.Enum("pending", "confirmed", "completed", "cancelled", "no_show"),
        nullable=False,
        default="pending",
    )
    is_skill_exchange = db.Column(db.Boolean, nullable=False, default=False)
    exchange_skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"))
    meeting_url = db.Column(db.String(500))
    tutor_joined_at = db.Column(db.DateTime)
    learner_joined_at = db.Column(db.DateTime)
    tutor_left_at = db.Column(db.DateTime)
    learner_left_at = db.Column(db.DateTime)
    both_joined_at = db.Column(db.DateTime)
    meeting_closed_at = db.Column(db.DateTime)
    tutor = db.relationship("User", foreign_keys=[tutor_id])
    learner = db.relationship("User", foreign_keys=[learner_id])
    skill = db.relationship("Skill", foreign_keys=[skill_id])
    exchange_skill = db.relationship("Skill", foreign_keys=[exchange_skill_id])


class Feedback(TimestampMixin, db.Model):
    __tablename__ = "feedback"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    session = db.relationship("Session")


class Rating(TimestampMixin, db.Model):
    __tablename__ = "ratings"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    rated_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating_value = db.Column(db.Integer, nullable=False)


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(80), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), index=True)
    session = db.relationship("Session")


class Report(TimestampMixin, db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    reported_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), index=True)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.Enum("low", "medium", "high"), nullable=False, default="medium")
    status = db.Column(db.Enum("open", "in_review", "resolved", "dismissed"), nullable=False, default="open")
    resolved_at = db.Column(db.DateTime)
    reporter = db.relationship("User", foreign_keys=[reporter_id])
    reported_user = db.relationship("User", foreign_keys=[reported_user_id])
    session = db.relationship("Session")


class RescheduleRequest(TimestampMixin, db.Model):
    __tablename__ = "reschedule_requests"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    proposed_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum("pending", "accepted", "declined"), nullable=False, default="pending")
    session = db.relationship("Session")
    requested_by = db.relationship("User")


class Message(TimestampMixin, db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    session = db.relationship("Session")
    sender = db.relationship("User")


class Payment(TimestampMixin, db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False, unique=True)
    payer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount_paise = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")
    provider = db.Column(db.String(40), nullable=False, default="manual")
    provider_reference = db.Column(db.String(255))
    status = db.Column(db.Enum("pending", "paid", "refunded", "failed"), nullable=False, default="pending")
    receipt_number = db.Column(db.String(80), unique=True, nullable=False)
    session = db.relationship("Session")
    payer = db.relationship("User")


class ReviewResponse(TimestampMixin, db.Model):
    __tablename__ = "review_responses"
    id = db.Column(db.Integer, primary_key=True)
    feedback_id = db.Column(db.Integer, db.ForeignKey("feedback.id"), nullable=False, unique=True)
    responder_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    feedback = db.relationship("Feedback")
    responder = db.relationship("User")


class Admin(TimestampMixin, db.Model):
    __tablename__ = "admins"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    permissions = db.Column(db.Text, nullable=False, default="")
