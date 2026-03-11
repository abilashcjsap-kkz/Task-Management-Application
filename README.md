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


## Task list filters
- In dashboard, Overall Task section supports **Task Created Date range** filtering.
- In Task List section, filter options include **Task Created Date range, Client, and Status**.

## Login page change password popup
- Click **Change Password** link on login page to open a popup form.
- Provide username, old password, new password and confirm password to update credentials.


## Member task action buttons
- Members get two task buttons:
  - **View Description** (popup showing manager-assigned task description)
  - **Add Daily Input** (popup to submit date-wise input notes)
- Managers/Admin can click **View Inputs** per task to see member-entered date-wise inputs.


## Member dashboard filters
- Members can filter task list by **Client**, **Assigned By**, **Allocated Date**, and **Status**.
