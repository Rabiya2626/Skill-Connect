from datetime import datetime, time, timedelta

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Notification, RescheduleRequest, Session, Skill, Tutor, TutorAvailability, User


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
        db.session.add(TutorAvailability(
            tutor_id=tutor.id,
            day_of_week=0,
            start_time=time(10),
            end_time=time(12),
            format="online",
        ))
        monday = datetime.utcnow() + timedelta(days=(7 - datetime.utcnow().weekday()) % 7 or 7)
        scheduled_at = monday.replace(hour=10, minute=0, second=0, microsecond=0)
        db.session.add(Session(
            tutor_id=tutor.id,
            learner_id=learner.id,
            skill_id=skill.id,
            scheduled_at=scheduled_at,
            duration_minutes=60,
            format="online",
            status="confirmed",
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


def user_ids(app):
    with app.app_context():
        return {
            user.email: user.id
            for user in User.query.filter(User.email.in_((
                "learner@example.com",
                "tutor@example.com",
                "outsider@example.com",
            ))).all()
        }


def proposed_time(app):
    with app.app_context():
        session = Session.query.one()
        return session.scheduled_at + timedelta(hours=1)


def test_learner_can_request_reschedule_and_tutor_is_notified(app):
    ids = user_ids(app)
    with app.test_client() as client:
        login(client, ids["learner@example.com"])
        response = client.post(
            "/sessions/1/reschedule",
            data={"proposed_at": proposed_time(app).isoformat()},
            follow_redirects=True,
        )

    assert response.status_code == 200
    with app.app_context():
        change = RescheduleRequest.query.one()
        assert change.requested_by_id == ids["learner@example.com"]
        assert change.status == "pending"
        assert change.proposed_at == proposed_time(app)
        assert Notification.query.filter_by(
            user_id=ids["tutor@example.com"], type="reschedule_request"
        ).count() == 1


def test_tutor_can_request_and_learner_can_decline_without_changing_session(app):
    ids = user_ids(app)
    with app.test_client() as tutor_client:
        login(tutor_client, ids["tutor@example.com"])
        response = tutor_client.post(
            "/sessions/1/reschedule",
            data={"proposed_at": proposed_time(app).isoformat()},
        )
        assert response.status_code == 302

    with app.app_context():
        change = RescheduleRequest.query.one()
        original_time = Session.query.one().scheduled_at
        request_id = change.id

    with app.test_client() as learner_client:
        login(learner_client, ids["learner@example.com"])
        response = learner_client.post(f"/reschedule-requests/{request_id}/decline")
        assert response.status_code == 302

    with app.app_context():
        assert RescheduleRequest.query.one().status == "declined"
        assert Session.query.one().scheduled_at == original_time


def test_accepting_reschedule_updates_session_and_marks_request_accepted(app):
    ids = user_ids(app)
    requested_time = proposed_time(app)
    with app.test_client() as client:
        login(client, ids["learner@example.com"])
        client.post(
            "/sessions/1/reschedule",
            data={"proposed_at": requested_time.isoformat()},
        )

    with app.app_context():
        request_id = RescheduleRequest.query.one().id

    with app.test_client() as client:
        login(client, ids["tutor@example.com"])
        response = client.post(f"/reschedule-requests/{request_id}/accept")
        assert response.status_code == 302

    with app.app_context():
        assert RescheduleRequest.query.one().status == "accepted"
        assert Session.query.one().scheduled_at == requested_time
        assert Notification.query.filter_by(
            user_id=ids["learner@example.com"], type="reschedule_accepted"
        ).count() == 1


@pytest.mark.parametrize("value", ["", "not-a-date"])
def test_invalid_proposed_time_is_rejected_without_creating_request(app, value):
    ids = user_ids(app)
    with app.test_client() as client:
        login(client, ids["learner@example.com"])
        response = client.post("/sessions/1/reschedule", data={"proposed_at": value})

    assert response.status_code == 302
    with app.app_context():
        assert RescheduleRequest.query.count() == 0


def test_past_time_and_nonparticipant_are_rejected(app):
    ids = user_ids(app)
    with app.test_client() as client:
        login(client, ids["learner@example.com"])
        response = client.post(
            "/sessions/1/reschedule",
            data={"proposed_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()},
        )
        assert response.status_code == 302

    with app.test_client() as client:
        login(client, ids["outsider@example.com"])
        response = client.post(
            "/sessions/1/reschedule",
            data={"proposed_at": proposed_time(app).isoformat()},
        )
        assert response.status_code in (403, 404)

    with app.app_context():
        assert RescheduleRequest.query.count() == 0
