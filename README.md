# Track Management Application

Track Management Application is a Flask-based portal for Admins, Managers, and Members to manage clients, tasks, timesheets, attendance, and reporting.

## Role capabilities

### Admin
- Manage client list (add/update/delete only by Admin)
- Manage members (create/delete/reset password)
- Assign tasks to members
- Extend due dates
- View overall task/attendance status
- Download period-based task log report (Excel-compatible CSV)

### Manager
- Assign tasks to members
- Select client from dropdown during task allocation
- Extend due dates
- View overall task/attendance status
- Submit attendance
- Download period-based task log report

### Member
- View assigned tasks with **Client**, **Allocated Date**, and **Due Date**
- Update task status
- Enter or revise logged hours (timesheet logs)
- Submit attendance

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
- `member / member123`

## How to test it

```bash
python3 -m compileall app.py templates static tests/test_app.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Manual smoke test:
1. Login as **Admin** and open **Clients** page; add/update/delete a client.
2. Login as **Manager** and create a task selecting a client and due date.
3. Login as **Member**, verify task shows client + allocated date + due date, then log hours.
4. Submit attendance as Member and Manager.
5. Login as Admin/Manager and download logs using date range on dashboard.
