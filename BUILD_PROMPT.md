# Build SkillConnect — Full-Stack Prompt for Codex

Copy everything below into Codex (or any VS Code AI agent) as your first message in a fresh project folder.

---

## Prompt

Build a full-stack web application called **SkillConnect — Skill Exchange and Peer Tutoring Platform** from scratch. I have working UI/HTML mockups for every page that you must use as the exact visual and structural reference — do not redesign them, convert them.

### Reference files (already in this repo, under `design-reference/`)
- `index.html` — marketing home/landing page
- `dashboard.html` — logged-in user dashboard
- `browse.html` — browse/search tutors & skills
- `tutor-profile.html` — individual tutor profile page
- `booking.html` — session booking flow (time picker → confirmation)
- `admin.html` — admin console
- `style.css` — shared design system (colors, type, components) used by all six pages

Read every file in `design-reference/` before writing any code. Preserve their layout, class names, component structure (especially the `.ticket`, `.card`, `.sidebar`, `.topbar`, `.stat-grid` patterns) and the CSS custom properties defined at the top of `style.css` (`--ink`, `--amber`, `--teal`, `--paper`, font variables, etc.). Do not introduce a different color palette, font stack, or component style — extend the existing system to any page not covered by the mockups (e.g. login/register, my-skills, my-exchanges, notifications).

### Tech stack
- Backend: Python 3 + Flask (application factory pattern, blueprints per module)
- Database: MySQL, accessed via SQLAlchemy ORM + Flask-Migrate for migrations
- Templating: Jinja2 — convert the static mockups into a `base.html` layout plus page templates that extend it
- Frontend: the existing HTML5/CSS3/vanilla JS from the mockups (no frontend framework)
- Auth: Flask-Login with hashed passwords (werkzeug.security)
- Forms: Flask-WTF with CSRF protection
- Environment/config: `.env` file via python-dotenv, `config.py` with Dev/Prod config classes

### Step 1 — Extract the shared shell
Before converting individual pages, extract the parts that repeat across `dashboard.html`, `browse.html`, `tutor-profile.html`, `booking.html`, and `admin.html` into reusable Jinja partials:
- `templates/base.html` — `<head>`, font links, `style.css` link
- `templates/partials/sidebar.html` — the app sidebar nav, parameterized so the active nav item is set per-page and the admin sidebar (from `admin.html`) is used when `current_user` is an admin
- `templates/partials/topbar.html` — search bar + top-right actions, parameterized per page

`index.html` (marketing) keeps its own separate `templates/marketing_base.html` since it uses a different nav (`.nav-marketing`) and has no sidebar.

### Step 2 — Database schema
Create SQLAlchemy models for these tables (infer sensible columns, types, and foreign keys; add `created_at`/`updated_at` timestamps to all):
- **Users** (id, name, email, password_hash, role [learner/tutor/both/admin], profile_picture_url, bio, is_verified, is_active)
- **Skills** (id, name, category, description)
- **UserSkills** (user_id, skill_id, type [offering/wanted], proficiency_level)
- **Tutors** (user_id, approved_by_admin, avg_rating, session_count, response_rate)
- **Learners** (user_id, learning_goals)
- **TutoringRequests** (id, learner_id, tutor_id, skill_id, status [pending/accepted/rejected], message, requested_at)
- **Sessions** (id, tutor_id, learner_id, skill_id, scheduled_at, duration_minutes, format [online/in_person], status [confirmed/completed/cancelled/no_show], is_skill_exchange, exchange_skill_id)
- **Feedback** (id, session_id, from_user_id, to_user_id, comment)
- **Ratings** (id, session_id, rated_user_id, rating_value 1–5)
- **Notifications** (id, user_id, type, message, is_read, created_at)
- **Admin** (user_id, permissions)

Write the models, then generate an initial Alembic migration and a `seed.py` script that inserts realistic demo data matching what's shown in the mockups (e.g. Priya Sharma, Dev Kulkarni, Maya Reyes, Leah Tran, Owen Marsh, Rahul Nair — same names/skills/ratings used in `tutor-profile.html`, `browse.html`, and `admin.html`) so the app looks identical to the mockups on first run.

### Step 3 — Routes & pages (convert each mockup into a working page)
Build these Flask blueprints, wiring real queries in place of the mockups' hardcoded HTML:

1. **`auth`** — `/register`, `/login`, `/logout` (new pages, matching the existing design system — no mockup provided, so design them consistently with `style.css`)
2. **`main`** — `/` → converts `index.html`, pulling live counts (active students, skills listed, sessions this week) from the DB instead of hardcoded numbers
3. **`dashboard`** — `/dashboard` → converts `dashboard.html`: real upcoming sessions, suggested matches (simple query: users who offer skills this user wants), progress bars, recent activity feed
4. **`skills`** — `/browse` → converts `browse.html` with working filters (category chips, session type, format, min rating) as query params, server-rendered results, and search
5. **`skills`** (cont.) — my-skills CRUD pages (add/edit/delete skill) — no mockup exists; build them in the same design system as a simple form page using `.card` styling
6. **`tutors`** — `/tutor/<id>` → converts `tutor-profile.html` with real skills offered, availability, and reviews pulled from `Sessions`/`Ratings`/`Feedback`
7. **`booking`** — `/book/<tutor_id>` → converts `booking.html`: real available slots (derive from tutor's set availability minus already-booked `Sessions`), POST creates a `Sessions` row and, if skill-exchange is toggled, also updates `TutoringRequests`
8. **`sessions`** — session history, cancel session, session status pages (no mockup — reuse `.card`/table patterns from `admin.html`)
9. **`notifications`** — notification list/dropdown (no mockup — reuse the topbar bell icon and `.card` list pattern)
10. **`admin`** — `/admin` → converts `admin.html`: real stat cards, user management table with search/filter, tutor approval actions (approve/decline update `Tutors.approved_by_admin`), reports list, skills catalog CRUD

### Step 4 — Business logic
- Session booking must prevent double-booking a slot
- Tutor approval: a user becomes a visible/bookable tutor only after `Tutors.approved_by_admin = true`
- Ratings: after a session's `scheduled_at` has passed and status is `completed`, prompt both users for a rating/feedback; recompute the tutor's `avg_rating`
- Notifications: create a `Notification` row on session request, booking confirmation, session reminder (cron/scheduled job stub is fine), and new feedback
- Admin "Remove fake accounts": soft-delete via `is_active = false`, don't hard-delete

### Step 5 — Project structure
Use this layout:
```
skillconnect/
  app/
    __init__.py          # app factory
    models.py
    config.py
    auth/
    main/
    dashboard/
    skills/
    tutors/
    booking/
    sessions/
    notifications/
    admin/
    templates/
      base.html
      marketing_base.html
      partials/
      auth/
      main/
      dashboard/
      skills/
      tutors/
      booking/
      sessions/
      admin/
    static/
      css/style.css      # copied from design-reference, unmodified
      js/
  migrations/
  seed.py
  requirements.txt
  .env.example
  README.md
```

### Step 6 — Deliverables
- A working Flask app that runs with `flask run` against a local MySQL instance after `flask db upgrade` and `python seed.py`
- `README.md` with setup steps (create MySQL DB, `.env` vars, install requirements, migrate, seed, run)
- Every page reachable from the sidebar/topbar nav actually works and pulls from the DB — no remaining hardcoded mock content outside `seed.py`

Ask me before making structural decisions I haven't specified (e.g. exact availability-scheduling UI for tutors, exact notification triggers) rather than guessing silently. Build incrementally: scaffold the project + models + auth first, confirm it runs, then convert one page at a time in the order listed in Step 3.
