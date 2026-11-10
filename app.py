import os
import secrets
import sqlite3
from contextlib import closing
from functools import wraps
from pathlib import Path

import click
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


DEMO_EMAIL = "student@gibraltar.edu"
DEMO_PASSWORD = "learnflask"
SUBJECTS = ("Programming", "Databases", "Web development", "Computer systems")


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "local-demo-key-change-me"),
        DATABASE=str(Path(app.instance_path) / "student_demo.sqlite3"),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    init_db(app)

    @app.before_request
    def prepare_form_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)

    @app.context_processor
    def expose_form_token():
        return {"csrf_token": session.get("csrf_token", "")}

    def login_required(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for("login"))
            return view(**kwargs)

        return wrapped_view

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = (
            get_db().execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
            if user_id is not None
            else None
        )

    def validate_form_token():
        submitted = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(submitted, expected):
            abort(400, description="The form expired. Please go back and try again.")

    @app.route("/", methods=("GET", "POST"))
    def login():
        if g.user is not None:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            validate_form_token()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("That email and password combination was not recognised.", "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        tasks = get_db().execute(
            """SELECT id, title, subject, due_date, is_complete
               FROM tasks WHERE user_id = ?
               ORDER BY is_complete, due_date IS NULL, due_date, id DESC""",
            (g.user["id"],),
        ).fetchall()
        completed_count = sum(task["is_complete"] for task in tasks)
        return render_template(
            "dashboard.html",
            tasks=tasks,
            subjects=SUBJECTS,
            completed_count=completed_count,
            open_count=len(tasks) - completed_count,
        )

    @app.post("/tasks")
    @login_required
    def add_task():
        validate_form_token()
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "")
        due_date = request.form.get("due_date", "").strip() or None
        if not title or len(title) > 120:
            flash("Add a task title of 1–120 characters.", "error")
        elif subject not in SUBJECTS:
            flash("Choose one of the listed subjects.", "error")
        else:
            get_db().execute(
                "INSERT INTO tasks (user_id, title, subject, due_date) VALUES (?, ?, ?, ?)",
                (g.user["id"], title, subject, due_date),
            )
            get_db().commit()
            flash("Study task added.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/tasks/<int:task_id>/toggle")
    @login_required
    def toggle_task(task_id):
        validate_form_token()
        cursor = get_db().execute(
            """UPDATE tasks SET is_complete = 1 - is_complete
               WHERE id = ? AND user_id = ?""",
            (task_id, g.user["id"]),
        )
        if cursor.rowcount == 0:
            abort(404)
        get_db().commit()
        return redirect(url_for("dashboard"))

    @app.post("/tasks/<int:task_id>/delete")
    @login_required
    def delete_task(task_id):
        validate_form_token()
        cursor = get_db().execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, g.user["id"]),
        )
        if cursor.rowcount == 0:
            abort(404)
        get_db().commit()
        flash("Study task removed.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/logout")
    @login_required
    def logout():
        validate_form_token()
        session.clear()
        return redirect(url_for("login"))

    @app.cli.command("init-db")
    def init_db_command():
        """Create the tables and demo account if needed."""
        init_db(app)
        click.echo(f"Database ready: {app.config['DATABASE']}")

    return app


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with closing(sqlite3.connect(app.config["DATABASE"])) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                due_date TEXT,
                is_complete INTEGER NOT NULL DEFAULT 0 CHECK (is_complete IN (0, 1))
            );
            """
        )
        user = db.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
        if user is None:
            cursor = db.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD)),
            )
            user_id = cursor.lastrowid
            db.executemany(
                """INSERT INTO tasks (user_id, title, subject, due_date)
                   VALUES (?, ?, ?, ?)""",
                [
                    (user_id, "Build a Python function", "Programming", "2026-11-18"),
                    (user_id, "Practise SELECT and JOIN queries", "Databases", "2026-11-20"),
                    (user_id, "Sketch a responsive page layout", "Web development", None),
                ],
            )
        db.commit()


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
