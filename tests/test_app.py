import re
import tempfile
import unittest
from pathlib import Path

from app import DEMO_EMAIL, DEMO_PASSWORD, create_app


class StudentHubTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test.sqlite3")
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key",
                "DATABASE": database,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def token_from(self, response):
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def login(self):
        response = self.client.get("/")
        return self.client.post(
            "/",
            data={
                "csrf_token": self.token_from(response),
                "email": DEMO_EMAIL,
                "password": DEMO_PASSWORD,
            },
            follow_redirects=True,
        )

    def test_login_shows_demo_and_rejects_bad_password(self):
        response = self.client.get("/")
        self.assertIn(b"student@gibraltar.edu", response.data)
        failed = self.client.post(
            "/",
            data={
                "csrf_token": self.token_from(response),
                "email": DEMO_EMAIL,
                "password": "wrong",
            },
        )
        self.assertIn(b"was not recognised", failed.data)

    def test_tasks_are_persisted_and_can_be_completed_and_removed(self):
        response = self.login()
        self.assertIn(b"Build a Python function", response.data)
        token = self.token_from(response)

        response = self.client.post(
            "/tasks",
            data={
                "csrf_token": token,
                "title": "Review recursion",
                "subject": "Programming",
                "due_date": "2026-12-01",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Review recursion", response.data)
        with self.app.app_context():
            from app import get_db

            task = get_db().execute(
                "SELECT id, is_complete FROM tasks WHERE title = ?", ("Review recursion",)
            ).fetchone()
        self.assertIsNotNone(task)

        self.client.post(
            f"/tasks/{task['id']}/toggle",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        with self.app.app_context():
            from app import get_db

            completed = get_db().execute(
                "SELECT is_complete FROM tasks WHERE id = ?", (task["id"],)
            ).fetchone()
        self.assertEqual(completed["is_complete"], 1)

        self.client.post(
            f"/tasks/{task['id']}/delete",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        with self.app.app_context():
            from app import get_db

            removed = get_db().execute(
                "SELECT id FROM tasks WHERE id = ?", (task["id"],)
            ).fetchone()
        self.assertIsNone(removed)

    def test_dashboard_requires_login_and_forms_require_csrf(self):
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        response = self.login()
        bad_post = self.client.post(
            "/tasks",
            data={"title": "No token", "subject": "Programming"},
        )
        self.assertEqual(bad_post.status_code, 400)
        self.assertIn(b"Build a Python function", response.data)


if __name__ == "__main__":
    unittest.main()
