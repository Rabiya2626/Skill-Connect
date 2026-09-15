import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Skill, Tutor, User, UserSkill


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    app.config["SECRET_KEY"] = "test-secret"
    with app.app_context():
        db.drop_all()
        db.create_all()
        skill = Skill(name="Python", category="Technology")
        learner = User(name="Learner", email="learner@example.com", role="learner")
        tutor = User(name="Tutor", email="tutor@example.com", role="tutor")
        both = User(name="Both", email="both@example.com", role="both")
        for user in (learner, tutor, both):
            user.set_password("secret")
        db.session.add_all([skill, learner, tutor, both])
        db.session.flush()
        db.session.add_all([Tutor(user_id=tutor.id), Tutor(user_id=both.id)])
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def get_user(app, email):
    with app.app_context():
        return User.query.filter_by(email=email).one()


def add_skill(client, skill_type):
    return client.post("/my-skills", data={
        "name": "Python",
        "category": "Technology",
        "type": skill_type,
        "proficiency_level": "Advanced",
    }, follow_redirects=True)


def test_learner_gets_only_learning_direction_and_cannot_offer(app):
    learner = get_user(app, "learner@example.com")
    with app.test_client() as client:
        login(client, learner.id)
        page = client.get("/my-skills")
        assert b"I want to learn this" in page.data
        assert b"I can offer this" not in page.data
        response = add_skill(client, "offering")
        assert response.status_code == 200

    with app.app_context():
        assert UserSkill.query.filter_by(user_id=learner.id).count() == 0


def test_tutor_gets_only_offering_direction_and_cannot_want(app):
    tutor = get_user(app, "tutor@example.com")
    with app.test_client() as client:
        login(client, tutor.id)
        page = client.get("/my-skills")
        assert b"I can offer this" in page.data
        assert b"I want to learn this" not in page.data
        response = add_skill(client, "wanted")
        assert response.status_code == 200

    with app.app_context():
        assert UserSkill.query.filter_by(user_id=tutor.id).count() == 0
        with app.test_client() as client:
            login(client, tutor.id)
            add_skill(client, "offering")
        assert UserSkill.query.filter_by(user_id=tutor.id, type="offering").count() == 1


def test_both_can_add_both_directions_and_access_exchanges(app):
    both = get_user(app, "both@example.com")
    with app.test_client() as client:
        login(client, both.id)
        page = client.get("/my-skills")
        assert b"I can offer this" in page.data
        assert b"I want to learn this" in page.data
        assert add_skill(client, "offering").status_code == 200
        assert add_skill(client, "wanted").status_code == 200
        assert client.get("/exchanges").status_code == 200

    with app.app_context():
        assert UserSkill.query.filter_by(user_id=both.id, type="offering").count() == 1
        assert UserSkill.query.filter_by(user_id=both.id, type="wanted").count() == 1


@pytest.mark.parametrize("email", ["learner@example.com", "tutor@example.com"])
def test_non_both_users_cannot_access_exchanges(app, email):
    user = get_user(app, email)
    with app.test_client() as client:
        login(client, user.id)
        page = client.get("/dashboard")
        assert b"Two-way Exchange Matches" not in page.data
        assert b"My exchanges" not in page.data
        assert client.get("/exchanges").status_code == 403


def test_learner_can_still_browse_tutors(app):
    learner = get_user(app, "learner@example.com")
    tutor = get_user(app, "tutor@example.com")
    with app.app_context():
        skill = Skill.query.filter_by(name="Python").one()
        db.session.add(UserSkill(user_id=tutor.id, skill_id=skill.id, type="offering", proficiency_level="Advanced"))
        db.session.commit()

    with app.test_client() as client:
        login(client, learner.id)
        response = client.get("/browse?q=Python")
        assert response.status_code == 200
        assert b"Tutor" in response.data
