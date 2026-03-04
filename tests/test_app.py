import os
import tempfile
import unittest

import app as track_app


class TrackManagementAppTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_track_management.db")
        track_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        track_app.DATABASE = self.db_path
        track_app.init_db()
        self.client = track_app.app.test_client()

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

        with track_app.app.app_context():
            db = track_app.get_db()
            row = db.execute("SELECT id FROM clients WHERE name = 'Acme'").fetchone()

        update_resp = self.client.post(f"/clients/{row['id']}/update", data={"name": "Acme Inc", "description": "Updated"}, follow_redirects=True)
        self.assertIn(b"Client updated", update_resp.data)

    def test_manager_assigns_task_with_client_and_due_date(self):
        self.login("manager", "manager123")
        with track_app.app.app_context():
            db = track_app.get_db()
            client_id = db.execute("SELECT id FROM clients LIMIT 1").fetchone()["id"]

        resp = self.client.post(
            "/tasks/create",
            data={
                "title": "Prepare release",
                "description": "v1 planning",
                "client_id": str(client_id),
                "assigned_to": "3",
                "due_date": "2030-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Task created successfully", resp.data)

    def test_member_updates_task_and_logs_hours(self):
        self.login("admin", "admin123")
        with track_app.app.app_context():
            db = track_app.get_db()
            client_id = db.execute("SELECT id FROM clients LIMIT 1").fetchone()["id"]

        self.client.post(
            "/tasks/create",
            data={
                "title": "Documentation",
                "description": "Write docs",
                "client_id": str(client_id),
                "assigned_to": "3",
                "due_date": "2030-01-01",
            },
            follow_redirects=True,
        )
        self.logout()
        self.login("member", "member123")

        with track_app.app.app_context():
            db = track_app.get_db()
            task_id = db.execute("SELECT id FROM tasks LIMIT 1").fetchone()["id"]

        resp = self.client.post(
            f"/tasks/{task_id}/update",
            data={"status": "in_progress", "log_date": "2030-01-02", "hours": "4", "notes": "Initial draft"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Task and timesheet updated", resp.data)

    def test_attendance_and_report(self):
        self.login("manager", "manager123")
        att_resp = self.client.post(
            "/attendance",
            data={"attendance_date": "2030-01-02", "status": "present", "remarks": "On time"},
            follow_redirects=True,
        )
        self.assertEqual(att_resp.status_code, 200)

        report_resp = self.client.get("/reports/task-logs?start_date=2030-01-01&end_date=2030-01-31")
        self.assertEqual(report_resp.status_code, 200)
        self.assertEqual(report_resp.mimetype, "text/csv")


if __name__ == "__main__":
    unittest.main()
