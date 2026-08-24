import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Notification, Session, Skill, Tutor, TutorAvailability, User, UserSkill
from datetime import datetime, time, timedelta


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    app.config['SECRET_KEY'] = 'test-secret'
    with app.app_context():
        db.drop_all()
        db.create_all()
        learner = User(name='Learner', email='learner@example.com', role='learner', is_verified=True)
        learner.set_password('secret')
        tutor = User(name='Tutor', email='tutor@example.com', role='tutor', is_verified=True)
        tutor.set_password('secret')
        db.session.add_all([learner, tutor])
        db.session.flush()
        db.session.add(Tutor(user_id=tutor.id, approved_by_admin=True, avg_rating=4.8, session_count=3, response_rate=95))
        skill = Skill(name='Python', category='Technology')
        db.session.add(skill)
        db.session.flush()
        db.session.add(UserSkill(user_id=learner.id, skill_id=skill.id, type='wanted', proficiency_level='beginner'))
        db.session.add(UserSkill(user_id=tutor.id, skill_id=skill.id, type='offering', proficiency_level='advanced'))
        db.session.add(TutorAvailability(tutor_id=tutor.id, day_of_week=0, start_time=time(10), end_time=time(11), format='online'))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_tutor_can_accept_a_booking_request_and_unlock_the_video_room(app):
    with app.app_context():
        learner_id = User.query.filter_by(email='learner@example.com').first().id
        tutor_id = User.query.filter_by(email='tutor@example.com').first().id

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = str(learner_id)
            sess['_fresh'] = True
        next_monday = datetime.utcnow() + timedelta(days=(7 - datetime.utcnow().weekday()) % 7 or 7)
        scheduled_at = next_monday.replace(hour=10, minute=0, second=0, microsecond=0)
        response = client.post(f'/book/{tutor_id}', data={
            'scheduled_at': scheduled_at.isoformat(),
            'skill_id': '1',
            'duration_minutes': '60',
            'format': 'online',
            'is_skill_exchange': '',
            'exchange_skill_id': ''
        }, follow_redirects=True)
        assert response.status_code == 200
        with app.app_context():
            assert Session.query.count() == 1
            session_id = Session.query.first().id
            assert Session.query.first().status == 'pending'
            assert Notification.query.filter_by(user_id=tutor_id).count() == 1
            assert Notification.query.filter_by(user_id=learner_id).count() == 1

    with app.test_client() as tutor_client:
        with tutor_client.session_transaction() as sess:
            sess['_user_id'] = str(tutor_id)
            sess['_fresh'] = True
        response = tutor_client.post(f'/sessions/{session_id}/respond/accept')
        assert response.status_code == 302
        with app.app_context():
            assert db.session.get(Session, session_id).status == 'confirmed'
            assert Notification.query.filter_by(user_id=learner_id, type='booking_accepted').count() == 1
        assert tutor_client.get(f'/session/{session_id}/meet').status_code == 200
