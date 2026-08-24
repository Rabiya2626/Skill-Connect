import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Skill, Tutor, User, UserSkill


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config["SECRET_KEY"] = "test-secret"
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login_client(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def test_browse_excludes_current_user(client, app):
    current_user = User(name="Me", email="me@example.com", role="learner")
    current_user.set_password("secret")
    other_user = User(name="Other Tutor", email="other@example.com", role="tutor")
    other_user.set_password("secret")

    skill = Skill(name="Python", category="Programming")
    db.session.add_all([current_user, other_user, skill])
    db.session.flush()

    db.session.add(UserSkill(user_id=other_user.id, skill_id=skill.id, type="offering", proficiency_level="advanced"))
    db.session.add(Tutor(user_id=other_user.id, approved_by_admin=True, avg_rating=0, session_count=0, response_rate=0))
    db.session.commit()

    login_client(client, current_user)

    response = client.get("/browse")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Other Tutor" in body
    assert "<h3>Me</h3>" not in body


def test_booking_page_offers_default_slots_when_tutor_has_no_availability(client, app):
    learner = User(name="Learner", email="learner@example.com", role="learner")
    learner.set_password("secret")
    tutor_user = User(name="Tutor User", email="tutor@example.com", role="tutor")
    tutor_user.set_password("secret")

    skill = Skill(name="React", category="Programming")
    db.session.add_all([learner, tutor_user, skill])
    db.session.flush()

    db.session.add(UserSkill(user_id=tutor_user.id, skill_id=skill.id, type="offering", proficiency_level="intermediate"))
    db.session.add(Tutor(user_id=tutor_user.id, approved_by_admin=True, avg_rating=0, session_count=0, response_rate=0))
    db.session.commit()

    login_client(client, learner)

    response = client.get(f"/book/{tutor_user.id}")

    assert response.status_code == 200
    assert b"Book a session" in response.data
    assert b"weekday slot" in response.data


def test_browse_only_shows_approved_tutors_and_honors_rating_filter(client, app):
    learner = User(name="Learner", email="learner-filter@example.com", role="learner")
    approved = User(name="Approved", email="approved@example.com", role="tutor")
    pending = User(name="Pending", email="pending@example.com", role="tutor")
    for user in (learner, approved, pending):
        user.set_password("secret")
    skill = Skill(name="Design", category="Creative")
    db.session.add_all([learner, approved, pending, skill])
    db.session.flush()
    db.session.add_all([
        Tutor(user_id=approved.id, approved_by_admin=True, avg_rating=4.9, session_count=1, response_rate=90),
        Tutor(user_id=pending.id, approved_by_admin=False, avg_rating=5, session_count=1, response_rate=90),
        UserSkill(user_id=approved.id, skill_id=skill.id, type="offering", proficiency_level="Advanced"),
        UserSkill(user_id=pending.id, skill_id=skill.id, type="offering", proficiency_level="Advanced"),
    ])
    db.session.commit()
    login_client(client, learner)

    response = client.get("/browse?minimum_rating=4.5&sort=rating")

    assert b"Approved" in response.data
    assert b"Pending" not in response.data
