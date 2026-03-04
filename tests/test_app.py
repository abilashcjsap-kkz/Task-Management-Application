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

    def test_admin_can_manage_clients(self):
        self.login("admin", "admin123")
        create_resp = self.client.post("/clients", data={"name": "Acme", "description": "Enterprise"}, follow_redirects=True)
        self.assertEqual(create_resp.status_code, 200)
        self.assertIn(b"Client added successfully", create_resp.data)

    def test_admin_can_create_member_with_email(self):
        self.login("admin", "admin123")
        create_member_resp = self.client.post(
            "/members",
            data={"username": "john", "email": "john@example.com", "password": "pass123"},
            follow_redirects=True,
        )
        self.assertEqual(create_member_resp.status_code, 200)
        self.assertIn(b"Member created successfully", create_member_resp.data)

    def test_manager_assigns_task_with_client_and_due_date(self):
        self.login("manager", "manager123")
        with task_app.app.app_context():
            db = task_app.get_db()
            client_id = db.execute("SELECT id FROM clients LIMIT 1").fetchone()["id"]

        resp = self.client.post(
            "/tasks/create",
            data={
                "client_id": str(client_id),
                "title": "Prepare release",
                "description": "v1 planning",
                "assigned_to": "3",
                "due_date": "2030-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Task created successfully", resp.data)

    def test_member_updates_status_and_hours_directly(self):
        self.login("admin", "admin123")
        with task_app.app.app_context():
            db = task_app.get_db()
            client_id = db.execute("SELECT id FROM clients LIMIT 1").fetchone()["id"]

        self.client.post(
            "/tasks/create",
            data={
                "client_id": str(client_id),
                "title": "Documentation",
                "description": "Write docs",
                "assigned_to": "3",
                "due_date": "2030-01-01",
            },
            follow_redirects=True,
        )
        self.logout()

        self.login("member", "member123")
        with task_app.app.app_context():
            db = task_app.get_db()
            task_id = db.execute("SELECT id FROM tasks LIMIT 1").fetchone()["id"]

        resp = self.client.post(
            f"/tasks/{task_id}/update",
            data={"status": "in_progress", "hours_spent": "4.5"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Task updated successfully", resp.data)

    def test_manager_can_download_report(self):
        self.login("manager", "manager123")
        report_resp = self.client.get("/reports/task-logs?start_date=2030-01-01&end_date=2030-01-31")
        self.assertEqual(report_resp.status_code, 200)
        self.assertEqual(report_resp.mimetype, "text/csv")


if __name__ == "__main__":
    unittest.main()
