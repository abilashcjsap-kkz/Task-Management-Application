# Task Management Application

Task Management Application is a Flask-based portal for Admins, Managers, and Members to manage clients, users, tasks, and reporting.

## Role capabilities

### Admin
- Manage client list (add/update/delete)
- Add users with **Name, Mail Id, Password, and Role (Member/Manager)**
- Reset password/delete users (for manager/member)
- Assign tasks to members
- Extend due dates
- View overall task status
- Download period-based task report (Excel-compatible CSV)

### Manager
- Allocate tasks to members
- Multiple managers can assign tasks to multiple members
- Extend due dates
- View overall task status
- Download period-based task report

### Member
- View assigned tasks with **Client**, **Allocated Date**, and **Due Date**
- Update only the **hours taken** for assigned tasks

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

Manual smoke test:
1. Login as **Admin** and create both manager and member users from Users page.
2. Login as **manager** and create tasks for members.
3. Login as **manager2** and create additional tasks for members.
4. Login as **member** and update only hours for assigned tasks.
5. Login as Admin/Manager and download report using date range on dashboard.
