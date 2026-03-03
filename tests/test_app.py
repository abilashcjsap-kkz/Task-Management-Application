import os
import tempfile
import unittest

import app as task_app


class TaskManagementAppTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_task_manager.db")

        task_app.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
        )
        task_app.DATABASE = self.db_path

        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        task_app.init_db()

        self.client = task_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username, password):
        return self.client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def logout(self):
        return self.client.get("/logout", follow_redirects=True)

    def test_seed_users_can_login(self):
        response = self.login("admin", "admin123")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Overall Task Status", response.data)

        self.logout()

        response = self.login("manager", "manager123")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Overall Task Status", response.data)

        self.logout()

        response = self.login("member", "member123")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"My Tasks", response.data)

    def test_admin_member_management_and_task_assignment_flow(self):
        self.login("admin", "admin123")

        create_member_response = self.client.post(
            "/members",
            data={"username": "new_member", "password": "pass123"},
            follow_redirects=True,
        )
        self.assertEqual(create_member_response.status_code, 200)
        self.assertIn(b"Member created successfully", create_member_response.data)

        with task_app.app.app_context():
            db = task_app.get_db()
            member = db.execute(
                "SELECT id FROM users WHERE username = ?", ("new_member",)
            ).fetchone()

        assign_task_response = self.client.post(
            "/tasks/create",
            data={
                "title": "Write tests",
                "description": "Cover key paths",
                "assigned_to": str(member["id"]),
                "hours_allocated": "3.5",
            },
            follow_redirects=True,
        )
        self.assertEqual(assign_task_response.status_code, 200)
        self.assertIn(b"Task created and assigned successfully", assign_task_response.data)

    def test_member_updates_task_status_and_hours(self):
        self.login("admin", "admin123")
        create_task_response = self.client.post(
            "/tasks/create",
            data={
                "title": "Initial Task",
                "description": "For member update",
                "assigned_to": "3",
                "hours_allocated": "2",
            },
            follow_redirects=True,
        )
        self.assertEqual(create_task_response.status_code, 200)
        self.logout()

        self.login("member", "member123")

        with task_app.app.app_context():
            db = task_app.get_db()
            task = db.execute("SELECT id FROM tasks LIMIT 1").fetchone()

        update_task_response = self.client.post(
            f"/tasks/{task['id']}/update",
            data={"status": "done", "hours_spent": "2"},
            follow_redirects=True,
        )
        self.assertEqual(update_task_response.status_code, 200)
        self.assertIn(b"Task updated successfully", update_task_response.data)

    def test_role_restrictions(self):
        self.login("member", "member123")
        forbidden_task_create = self.client.post(
            "/tasks/create",
            data={
                "title": "Should fail",
                "description": "Member cannot assign",
                "assigned_to": "3",
                "hours_allocated": "1",
            },
            follow_redirects=True,
        )
        self.assertEqual(forbidden_task_create.status_code, 200)
        self.assertIn(b"not authorized", forbidden_task_create.data)

        self.logout()

        self.login("manager", "manager123")
        forbidden_member_page = self.client.get("/members", follow_redirects=True)
        self.assertEqual(forbidden_member_page.status_code, 200)
        self.assertIn(b"not authorized", forbidden_member_page.data)


if __name__ == "__main__":
    unittest.main()
