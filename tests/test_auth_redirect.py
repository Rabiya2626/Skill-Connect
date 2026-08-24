import unittest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User


class AuthRedirectTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app.config["SECRET_KEY"] = "test-secret"
        with self.app.app_context():
            db.create_all()
            user = User(name="Anita", email="anita@example.com", role="admin")
            user.set_password("SkillConnect123!")
            db.session.add(user)
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(
            "/login",
            data={"email": "anita@example.com", "password": "SkillConnect123!"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard")


if __name__ == "__main__":
    unittest.main()
