from app import create_app
from app.auth.routes import _account_token
from app.config import TestingConfig
from app.extensions import db
from app.models import Learner, User


def make_app():
    app = create_app(TestingConfig)
    app.config["SECRET_KEY"] = "test-secret"
    with app.app_context():
        db.create_all()
    return app


def test_registration_requires_terms_and_verification_token_works():
    app = make_app()
    client = app.test_client()
    response = client.post("/register", data={
        "name": "New User", "email": "new@example.com", "role": "learner",
        "bio": "", "password": "a-secure-password", "confirm_password": "a-secure-password",
    })
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="new@example.com").first() is None

        user = User(name="Verify Me", email="verify@example.com", role="learner")
        user.set_password("a-secure-password")
        db.session.add(user)
        db.session.commit()
        token = _account_token(user, "verify")

    response = client.get(f"/verify-email/{token}")
    assert response.status_code == 302
    with app.app_context():
        assert User.query.filter_by(email="verify@example.com").first().is_verified is True
        db.session.remove()
        db.drop_all()


def test_forgot_password_uses_generic_message_for_unknown_email():
    app = make_app()
    client = app.test_client()

    response = client.post("/forgot-password", data={"email": "missing@example.com"}, follow_redirects=True)

    assert response.status_code == 200
    assert b"If an account exists for this email, a password reset link has been sent." in response.data

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_invalid_reset_token_shows_expired_message():
    app = make_app()
    client = app.test_client()

    response = client.get("/reset-password/not-a-valid-token", follow_redirects=True)

    assert response.status_code == 200
    assert b"This password reset link is invalid or has expired. Please request a new reset link." in response.data

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_profile_update_persists_portfolio_and_learning_goals():
    app = make_app()
    with app.app_context():
        user = User(name="Learner", email="learner@example.com", role="learner")
        user.set_password("a-secure-password")
        user.learner = Learner()
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    response = client.post("/profile", data={
        "name": "Updated Learner", "bio": "Learning deliberately.",
        "learning_goals": "Build a portfolio", "profile_picture_url": "",
        "portfolio_url": "https://example.com/portfolio", "certificate_url": "",
    })
    assert response.status_code == 302
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.name == "Updated Learner"
        assert user.portfolio_url == "https://example.com/portfolio"
        assert user.learner.learning_goals == "Build a portfolio"
        db.session.remove()
        db.drop_all()
