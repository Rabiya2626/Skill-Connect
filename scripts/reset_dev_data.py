#!/usr/bin/env python3
"""Development-only cleanup for SkillConnect user-generated data.

This script removes all non-admin users and dependent records from the local
Flask development database while preserving schema, migrations, admin accounts,
and system/reference data such as skills/categories.

Safety rules:
- It refuses to run unless the app is clearly in a development/testing config.
- It refuses to run if the database does not look local (127.0.0.1/localhost or sqlite).
- It requires a --yes flag before deleting anything.
"""

import argparse
import os
import sys

from sqlalchemy import or_

from app import create_app
from app.extensions import db
from app.models import (
    Admin,
    Feedback,
    Learner,
    Message,
    Notification,
    Payment,
    Rating,
    Report,
    RescheduleRequest,
    ReviewResponse,
    Session,
    Skill,
    Tutor,
    TutorAvailability,
    User,
    UserSkill,
)


def is_local_dev_environment(app):
    env = (os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or app.config.get("ENV") or "").lower()
    db_uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    debug = bool(app.config.get("DEBUG"))
    local_like = "127.0.0.1" in db_uri or "localhost" in db_uri or "sqlite" in db_uri
    if env in {"development", "testing"} and local_like:
        return True
    # Also guard against accidental production-like config where debug is off.
    if debug and local_like and env not in {"production", "prod"}:
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Delete all non-admin user data from the local SkillConnect development database.")
    parser.add_argument("--yes", action="store_true", help="Required confirmation flag to proceed with cleanup.")
    args = parser.parse_args()

    if not args.yes:
        print("Refusing to run without --yes. This script intentionally requires explicit confirmation.")
        return 2

    app = create_app()
    with app.app_context():
        if not is_local_dev_environment(app):
            raise SystemExit(
                "Refusing to run cleanup: this is not a clearly local development/testing environment. "
                "This script is intentionally restricted to local development/test databases."
            )

        preserved_admin_ids = set(row[0] for row in db.session.query(User.id).filter(User.role == "admin").all())
        preserved_admin_ids |= set(row[0] for row in db.session.query(Admin.user_id).all())

        normal_user_ids = [
            row[0]
            for row in db.session.query(User.id)
            .filter(User.id.notin_(list(preserved_admin_ids) or [0]))
            .all()
        ]

        if not normal_user_ids:
            print("No normal users found to delete. Nothing changed.")
            print(f"Preserved admin users: {sorted(preserved_admin_ids)}")
            return 0

        session_ids = set(
            row[0]
            for row in db.session.query(Session.id)
            .filter(or_(Session.tutor_id.in_(normal_user_ids), Session.learner_id.in_(normal_user_ids)))
            .all()
        )
        feedback_ids = set(
            row[0]
            for row in db.session.query(Feedback.id)
            .filter(
                or_(
                    Feedback.session_id.in_(session_ids),
                    Feedback.from_user_id.in_(normal_user_ids),
                    Feedback.to_user_id.in_(normal_user_ids),
                )
            )
            .all()
        )

        deleted_counts = {}

        deleted_counts["review_responses"] = (
            db.session.query(ReviewResponse)
            .filter(ReviewResponse.feedback_id.in_(feedback_ids))
            .delete(synchronize_session=False)
            if feedback_ids
            else 0
        )
        deleted_counts["feedback"] = (
            db.session.query(Feedback)
            .filter(
                or_(
                    Feedback.session_id.in_(session_ids),
                    Feedback.from_user_id.in_(normal_user_ids),
                    Feedback.to_user_id.in_(normal_user_ids),
                )
            )
            .delete(synchronize_session=False)
        )
        deleted_counts["ratings"] = (
            db.session.query(Rating)
            .filter(or_(Rating.session_id.in_(session_ids), Rating.rated_user_id.in_(normal_user_ids)))
            .delete(synchronize_session=False)
        )
        deleted_counts["reports"] = (
            db.session.query(Report)
            .filter(
                or_(
                    Report.reporter_id.in_(normal_user_ids),
                    Report.reported_user_id.in_(normal_user_ids),
                    Report.session_id.in_(session_ids),
                )
            )
            .delete(synchronize_session=False)
        )
        deleted_counts["messages"] = (
            db.session.query(Message)
            .filter(or_(Message.sender_id.in_(normal_user_ids), Message.session_id.in_(session_ids)))
            .delete(synchronize_session=False)
        )
        deleted_counts["notifications"] = (
            db.session.query(Notification)
            .filter(or_(Notification.user_id.in_(normal_user_ids), Notification.session_id.in_(session_ids)))
            .delete(synchronize_session=False)
        )
        deleted_counts["payments"] = (
            db.session.query(Payment)
            .filter(or_(Payment.payer_id.in_(normal_user_ids), Payment.session_id.in_(session_ids)))
            .delete(synchronize_session=False)
        )
        deleted_counts["reschedule_requests"] = (
            db.session.query(RescheduleRequest)
            .filter(
                or_(
                    RescheduleRequest.requested_by_id.in_(normal_user_ids),
                    RescheduleRequest.session_id.in_(session_ids),
                )
            )
            .delete(synchronize_session=False)
        )
        deleted_counts["sessions"] = (
            db.session.query(Session)
            .filter(or_(Session.tutor_id.in_(normal_user_ids), Session.learner_id.in_(normal_user_ids)))
            .delete(synchronize_session=False)
        )
        deleted_counts["user_skills"] = (
            db.session.query(UserSkill)
            .filter(UserSkill.user_id.in_(normal_user_ids))
            .delete(synchronize_session=False)
        )
        deleted_counts["tutor_availability"] = (
            db.session.query(TutorAvailability)
            .filter(TutorAvailability.tutor_id.in_(normal_user_ids))
            .delete(synchronize_session=False)
        )
        deleted_counts["tutors"] = (
            db.session.query(Tutor).filter(Tutor.user_id.in_(normal_user_ids)).delete(synchronize_session=False)
        )
        deleted_counts["learners"] = (
            db.session.query(Learner).filter(Learner.user_id.in_(normal_user_ids)).delete(synchronize_session=False)
        )
        deleted_counts["users"] = (
            db.session.query(User)
            .filter(User.id.in_(normal_user_ids))
            .delete(synchronize_session=False)
        )

        db.session.commit()

        skill_count = db.session.query(Skill).count()
        remaining_user_count = db.session.query(User).count()
        remaining_admins = [
            (row[0], row[1], row[2])
            for row in db.session.query(User.id, User.name, User.email)
            .filter(User.role == "admin")
            .order_by(User.id)
            .all()
        ]

        print("Development database cleanup complete.")
        print(f"Preserved admin accounts: {remaining_admins}")
        print(f"Deleted non-admin user IDs: {sorted(normal_user_ids)}")
        print(f"Deleted summary: { {key: value for key, value in deleted_counts.items() if value} }")
        print(f"Remaining users: {remaining_user_count}")
        print(f"Skills/categories preserved: {skill_count}")

        return 0


if __name__ == "__main__":
    sys.exit(main())
