# University of Gibraltar · Computing Student Hub

A small Flask demonstrator for computer science students. Sign in, then manage
a personal study-task list backed by SQLite. The starter data gives the
dashboard something to show on first launch.

## Run locally

Requires Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
flask --app app run --debug
```

Open <http://127.0.0.1:5000>.

**Demo login:** `student@gibraltar.edu` / `learnflask`

The database is created automatically at `instance/student_demo.sqlite3`.
To initialize it explicitly, run `flask --app app init-db`.

## Try it

- Add tasks for Programming, Databases, Web development, or Computer systems.
- Optionally give a task a due date.
- Mark tasks complete or remove them; reload the page to see SQLite retain
  your changes.
- Sign out, then sign in again to see the same saved list.

## Teaching points

- `create_app()` wires up the app and makes it straightforward to test.
- `init_db()` creates the `users` and `tasks` tables and inserts starter data.
- `get_db()` opens a SQLite connection for the request; `close_db()` closes it.
- Routes use parameterized SQL, and each task query is scoped to the signed-in
  user.
- Passwords are stored as Werkzeug password hashes, not plain text.
- Forms use POST for changes and include a session CSRF token.

This is a classroom demo, not a production authentication system. It has one
seeded account and no account registration or password reset. The fallback
session key is for local demonstration only; set `FLASK_SECRET_KEY` to a
private random value before exposing the app beyond a local machine.

## Run tests

```powershell
python -m unittest discover -s tests
```
