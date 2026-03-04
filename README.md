# Task Management Application

Task Management Application is a Flask-based portal for Admins, Managers, and Members to manage clients, users, tasks, and reporting.

## Role capabilities

### Admin
- Manage client list (add/update/delete)
- Add users with **Name, Mail Id, Password, and Role (Member/Manager)**
- Reset password/delete users (for manager/member)
- Assign tasks to members
- Update status of every task
- Extend due dates
- View overall task status
- Download period-based task report (Excel-compatible CSV)

### Manager
- Allocate tasks to members
- Multiple managers can assign tasks to multiple members
- Update status of every task
- Extend due dates
- View overall task status
- Download period-based task report

### Member
- View assigned tasks with **Client**, **Allocated Date**, and **Due Date**
- Update status of assigned tasks
- Update hours taken for assigned tasks

## Password change
- Password can be changed from the **Login page** for Admin/Manager/Member.
- User must provide **username + old password + new password + confirm password**.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open: `http://localhost:5000`

## Demo users
- `admin / admin123`
- `manager / manager123`
- `manager2 / manager123`
- `member / member123`

## How to test it

```bash
python3 -m compileall app.py tests/test_app.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```
