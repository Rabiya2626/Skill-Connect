from datetime import datetime, time, timedelta

from app import create_app
from app.extensions import db
from app.models import Admin, Learner, Notification, Session, Skill, Tutor, TutorAvailability, User, UserSkill

app = create_app()

USERS = [
    ("Priya Sharma", "priya@example.com", "tutor", "Applied Mathematics senior who makes calculus feel practical.", 5.0, 92),
    ("Dev Kulkarni", "dev@example.com", "both", "Computer science student and enthusiastic guitar beginner.", 4.8, 32),
    ("Maya Reyes", "maya@example.com", "both", "Linguistics student offering conversational Spanish.", 4.9, 47),
    ("Leah Tran", "leah@example.com", "tutor", "Patient writing and academic presentation coach.", 4.7, 24),
    ("Owen Marsh", "owen@example.com", "tutor", "Photography, Lightroom and visual storytelling tutor.", 4.8, 19),
    ("Rahul Nair", "rahul@example.com", "learner", "Mechanical engineering student exploring code and music.", 0, 0),
    ("Anita Desai", "anita@example.com", "admin", "SkillConnect platform administrator.", 0, 0),
]

def get_skill(name, category):
    skill = Skill.query.filter_by(name=name).first()
    if not skill:
        skill = Skill(name=name, category=category)
        db.session.add(skill); db.session.flush()
    return skill

def attach(user, name, category, kind, level):
    skill = get_skill(name, category)
    if not UserSkill.query.filter_by(user_id=user.id, skill_id=skill.id, type=kind).first():
        db.session.add(UserSkill(user_id=user.id, skill_id=skill.id, type=kind, proficiency_level=level))
    return skill

with app.app_context():
    people = {}
    for name, email, role, bio, rating, sessions in USERS:
        person = User.query.filter_by(email=email).first()
        if not person:
            person = User(name=name, email=email, role=role, bio=bio, is_verified=True)
            person.set_password("SkillConnect123!")
            db.session.add(person); db.session.flush()
        people[name] = person
        if role in {"learner", "both"} and not person.learner: person.learner = Learner(learning_goals="Learn practical skills from peers.")
        if role in {"tutor", "both"} and not person.tutor: person.tutor = Tutor(approved_by_admin=True, avg_rating=rating, session_count=sessions, response_rate=98)
    if not db.session.get(Admin, people["Anita Desai"].id): db.session.add(Admin(user_id=people["Anita Desai"].id, permissions="users,skills,tutors,reports"))
    db.session.flush()

    calculus = attach(people["Priya Sharma"], "Calculus II", "Academic", "offering", "Advanced")
    attach(people["Priya Sharma"], "Data Visualization", "Technology", "offering", "Advanced")
    python = attach(people["Dev Kulkarni"], "Python", "Technology", "offering", "Advanced")
    attach(people["Dev Kulkarni"], "Guitar basics", "Music", "wanted", "Beginner")
    spanish = attach(people["Maya Reyes"], "Conversational Spanish", "Languages", "offering", "Advanced")
    attach(people["Maya Reyes"], "Python", "Technology", "wanted", "Beginner")
    attach(people["Leah Tran"], "Academic Writing", "Academic", "offering", "Advanced")
    attach(people["Owen Marsh"], "Photography", "Creative", "offering", "Advanced")
    attach(people["Rahul Nair"], "Calculus II", "Academic", "wanted", "Intermediate")

    for person in people.values():
        if person.tutor and not person.tutor.availability:
            db.session.add_all([TutorAvailability(tutor_id=person.id, day_of_week=1, start_time=time(10), end_time=time(13), format="online"), TutorAvailability(tutor_id=person.id, day_of_week=3, start_time=time(14), end_time=time(17), format="either")])
    if not Session.query.first():
        db.session.add(Session(tutor_id=people["Priya Sharma"].id, learner_id=people["Dev Kulkarni"].id, skill_id=calculus.id, scheduled_at=datetime.utcnow() + timedelta(days=2), duration_minutes=60, format="online"))
        db.session.add(Notification(user_id=people["Dev Kulkarni"].id, type="welcome", message="Welcome to SkillConnect — add skills to improve your matches."))
    db.session.commit()
    print("Seeded SkillConnect. Demo password for all accounts: SkillConnect123!")
