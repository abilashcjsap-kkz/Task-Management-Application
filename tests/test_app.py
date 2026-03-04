import os
import tempfile
import unittest

import app as task_app


class TaskManagementAppTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_task_management.db")
        task_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        task_app.DATABASE = self.db_path
        task_app.init_db()
        self.client = task_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username, password):
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def logout(self):
        self.client.get("/logout", follow_redirects=True)

    def test_admin_can_create_member_or_manager(self):
        self.login("admin", "admin123")
        create_manager = self.client.post(
            "/members",
            data={"username": "managerx", "email": "mx@example.com", "password": "pass123", "role": "manager"},
            follow_redirects=True,
        )
        self.assertEqual(create_manager.status_code, 200)
        self.assertIn(b"Manager created successfully", create_manager.data)

        create_member = self.client.post(
            "/members",
            data={"username": "memberx", "email": "ux@example.com", "password": "pass123", "role": "member"},
            follow_redirects=True,
        )
        self.assertEqual(create_member.status_code, 200)
        self.assertIn(b"Member created successfully", create_member.data)

    def test_multiple_managers_can_assign_tasks(self):
        with task_app.app.app_context():
            db = task_app.get_db()
            client_id = db.execute("SELECT id FROM clients LIMIT 1").fetchone()["id"]

        self.login("manager", "manager123")
        r1 = self.client.post(
            "/tasks/create",
            data={
                "client_id": str(client_id),
                "title": "Task by manager",
                "description": "first",
                "assigned_to": "4",
                "due_date": "2030-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(r1.status_code, 200)
        self.logout()

        self.login("manager2", "manager123")
        r2 = self.client.post(
            "/tasks/create",
            data={
                "client_id": str(client_id),
                "title": "Task by manager2",
                "description": "second",
                "assigned_to": "4",
                "due_date": "2030-01-02",
            },
            follow_redirects=True,
        )
        self.assertEqual(r2.status_code, 200)

    def test_member_can_only_update_hours_taken(self):
        with task_app.app.app_context():
            db = task_app.get_db()
            client_id = db.execute("SELECT id FROM clients LIMIT 1").fetchone()["id"]

        self.login("manager", "manager123")
        self.client.post(
            "/tasks/create",
            data={
                "client_id": str(client_id),
                "title": "Hours only",
                "description": "no status update",
                "assigned_to": "4",
                "due_date": "2030-01-01",
            },
            follow_redirects=True,
        )
        self.logout()

        self.login("member", "member123")
        with task_app.app.app_context():
            db = task_app.get_db()
            task_id = db.execute("SELECT id, status FROM tasks LIMIT 1").fetchone()["id"]

        resp = self.client.post(
            f"/tasks/{task_id}/update",
            data={"hours_spent": "5.25"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Hours updated successfully", resp.data)

        with task_app.app.app_context():
            db = task_app.get_db()
            task = db.execute("SELECT hours_spent, status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            self.assertEqual(task["status"], "todo")
            self.assertAlmostEqual(task["hours_spent"], 5.25)

    def test_manager_can_download_report(self):
        self.login("manager", "manager123")
        report_resp = self.client.get("/reports/task-logs?start_date=2030-01-01&end_date=2030-01-31")
        self.assertEqual(report_resp.status_code, 200)
        self.assertEqual(report_resp.mimetype, "text/csv")


if __name__ == "__main__":
    unittest.main()
