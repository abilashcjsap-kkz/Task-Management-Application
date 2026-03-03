# Task Management Application

A Flask-based task management application with role-based access for **Admin**, **Manager**, and **Member** users.

## Features

- **Admin**
  - Create member accounts
  - Delete member accounts
  - Reset member passwords
  - Assign tasks to members
  - View overall task status and progress
- **Manager**
  - Assign tasks to members
  - View overall task status and progress
- **Member**
  - View assigned tasks
  - Update task status (`todo`, `in_progress`, `done`)
  - Log hours spent on each task

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## Demo Credentials

- `admin / admin123`
- `manager / manager123`
- `member / member123`

These users are auto-created on first run.


## How to test it

Run these commands from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
```

Manual smoke test:

1. Start the app with `python app.py`.
2. Open `http://localhost:5000`.
3. Login as Admin (`admin/admin123`) and create a member from **Manage Members**.
4. Login as Manager and assign a task with allocated hours.
5. Login as Member and update task status + hours spent.
6. Login as Admin/Manager again and verify overall dashboard counts/hours.

