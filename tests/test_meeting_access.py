from datetime import datetime, timedelta

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Session, Skill, Tutor, User


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    app.config["SECRET_KEY"] = "test-secret"
    with app.app_context():
        db.drop_all()
        db.create_all()
        learner = User(name="Learner", email="learner@example.com", role="learner")
        tutor = User(name="Tutor", email="tutor@example.com", role="tutor")
        outsider = User(name="Outsider", email="outsider@example.com", role="learner")
        for user in (learner, tutor, outsider):
            user.set_password("secret")
        db.session.add_all([learner, tutor, outsider])
        db.session.flush()
        db.session.add(Tutor(user_id=tutor.id))
        skill = Skill(name="Python", category="Technology")
        db.session.add(skill)
        db.session.flush()
        db.session.add(Session(
            tutor_id=tutor.id,
            learner_id=learner.id,
            skill_id=skill.id,
            scheduled_at=datetime.utcnow() - timedelta(minutes=1),
            duration_minutes=60,
            format="online",
            status="confirmed",
            meeting_url="https://meet.jit.si/skillconnect-test",
        ))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def ids(app):
    with app.app_context():
        return {user.email: user.id for user in User.query.all()}


def test_join_is_rejected_before_scheduled_date_and_time(app):
    user_ids = ids(app)
    with app.app_context():
        session = Session.query.one()
        session.scheduled_at = datetime.utcnow() + timedelta(days=1)
        db.session.commit()

    with app.test_client() as client:
        login(client, user_ids["learner@example.com"])
        response = client.get("/session/1/meet", follow_redirects=True)
        assert response.status_code == 200
        assert b"You can join when the session begins" in response.data
        response = client.post("/sessions/1/meeting/join")
        assert response.status_code == 403


def test_tutor_and_learner_join_timestamps_are_recorded(app):
    user_ids = ids(app)
    with app.test_client() as tutor_client:
        login(tutor_client, user_ids["tutor@example.com"])
        assert tutor_client.get("/session/1/meet").status_code == 200
        assert tutor_client.post("/sessions/1/meeting/join").json == {"ok": True, "both_joined": False}

    with app.test_client() as learner_client:
        login(learner_client, user_ids["learner@example.com"])
        assert learner_client.post("/sessions/1/meeting/join").json == {"ok": True, "both_joined": True}

    with app.app_context():
        session = Session.query.one()
        assert session.tutor_joined_at is not None
        assert session.learner_joined_at is not None
        assert session.both_joined_at is not None


def test_leaving_before_five_minutes_does_not_close_session(app):
    user_ids = ids(app)
    with app.app_context():
        session = Session.query.one()
        session.tutor_joined_at = datetime.utcnow() - timedelta(minutes=2)
        session.learner_joined_at = datetime.utcnow() - timedelta(minutes=2)
        session.both_joined_at = datetime.utcnow() - timedelta(minutes=2)
        db.session.commit()

    with app.test_client() as tutor_client:
        login(tutor_client, user_ids["tutor@example.com"])
        assert tutor_client.post("/sessions/1/meeting/leave").json["closed"] is False
    with app.test_client() as learner_client:
        login(learner_client, user_ids["learner@example.com"])
        assert learner_client.post("/sessions/1/meeting/leave").json["closed"] is False

    with app.app_context():
        session = Session.query.one()
        assert session.status == "confirmed"
        assert session.meeting_closed_at is None


def test_both_participants_leaving_after_five_minutes_closes_session_and_blocks_rejoin(app):
    user_ids = ids(app)
    with app.app_context():
        session = Session.query.one()
        session.tutor_joined_at = datetime.utcnow() - timedelta(minutes=6)
        session.learner_joined_at = datetime.utcnow() - timedelta(minutes=6)
        session.both_joined_at = datetime.utcnow() - timedelta(minutes=6)
        db.session.commit()

    with app.test_client() as tutor_client:
        login(tutor_client, user_ids["tutor@example.com"])
        assert tutor_client.post("/sessions/1/meeting/leave").json["closed"] is False
    with app.test_client() as learner_client:
        login(learner_client, user_ids["learner@example.com"])
        assert learner_client.post("/sessions/1/meeting/leave").json["closed"] is True
        assert learner_client.post("/sessions/1/meeting/join").status_code == 409
        assert learner_client.get("/session/1/meet", follow_redirects=True).status_code == 200
        assert b"can no longer be rejoined" in learner_client.get("/session/1/meet", follow_redirects=True).data

    with app.test_client() as tutor_client:
        login(tutor_client, user_ids["tutor@example.com"])
        assert tutor_client.post("/sessions/1/meeting/join").status_code == 409

    with app.app_context():
        session = Session.query.one()
        assert session.status == "completed"
        assert session.meeting_closed_at is not None


def test_nonparticipant_and_cancelled_session_cannot_join(app):
    user_ids = ids(app)
    with app.test_client() as outsider_client:
        login(outsider_client, user_ids["outsider@example.com"])
        assert outsider_client.post("/sessions/1/meeting/join").status_code == 404

    with app.app_context():
        Session.query.one().status = "cancelled"
        db.session.commit()
    with app.test_client() as learner_client:
        login(learner_client, user_ids["learner@example.com"])
        assert learner_client.post("/sessions/1/meeting/join").status_code == 409
