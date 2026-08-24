# SkillConnect

A Flask and MySQL peer-tutoring platform based on the supplied SkillConnect design references.

## First increment

The initial scaffold includes the Flask application factory, SQLAlchemy data model, Flask-Migrate integration, CSRF-protected authentication, and a live-count marketing home page.

## Setup

1. Create a MySQL database named `skillconnect_db` and a user with access to it.
2. Create and activate a virtual environment, then install the packages:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set `DATABASE_URL` and `SECRET_KEY`. Use
   `127.0.0.1:3306` (rather than `localhost`) so SQLAlchemy connects over TCP.
4. Apply the included initial database migration:

   ```bash
   flask --app wsgi db upgrade
   ```

5. Run the app:

   ```bash
   flask --app wsgi run
   ```

   SkillConnect runs at `http://127.0.0.1:5001`. Port 5000 is commonly used
   by macOS services and may not be available.

6. Run the test suite:

   ```bash
   pytest -q
   ```

## Current routes

- `/` — marketing home with database-backed counts
- `/register` — create a learner, tutor, or combined profile
- `/login` and `/logout` — session authentication
- `/dashboard`, `/browse`, `/tutor/<id>`, and `/book/<tutor_id>` — discovery and booking
- `/sessions` and `/sessions/<id>/feedback` — history, cancellation, and feedback
- `/notifications` — notification list
- `/admin` — admin stats, users, skills, and tutor approvals

Tutor availability is stored as recurring weekly windows (`TutorAvailability`); booking derives the next two weeks of available one-hour slots and rejects a slot that has already been booked.

## Demo accounts

After seeding, all demo accounts use the password `SkillConnect123!`. Examples: `dev@example.com` and `anita@example.com` (admin).

## Free-tier integrations

Razorpay runs only in test mode. Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and
`RAZORPAY_WEBHOOK_SECRET` in the deployment environment. Configure its test webhook at
`https://<your-render-domain>/webhooks/razorpay`. Set `RESEND_API_KEY` and
`RESEND_FROM_EMAIL` for verification and password-reset email. Use a verified Resend
sender (or Resend's testing sender while developing). Never commit `.env`.

`render.yaml` provisions the free Render web service and `.github/workflows/test.yml`
runs the test suite on GitHub Actions. This is a server-rendered Flask application, so
Vercel is not required unless the frontend is later separated from the backend.
