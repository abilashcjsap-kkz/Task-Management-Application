import csv
import io
import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import Flask, Response, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "task_management.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_tasks_hours_column(db):
    cursor = db.execute("PRAGMA table_info(tasks)")
    columns = {row[1] for row in cursor.fetchall()}
    if "hours_spent" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN hours_spent REAL NOT NULL DEFAULT 0")


def init_db():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'member')),
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL CHECK(status IN ('todo', 'in_progress', 'done')) DEFAULT 'todo',
            client_id INTEGER NOT NULL,
            assigned_to INTEGER NOT NULL,
            assigned_by INTEGER NOT NULL,
            allocated_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            hours_spent REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id),
            FOREIGN KEY (assigned_by) REFERENCES users(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('present', 'absent', 'half_day', 'leave')),
            remarks TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (user_id, attendance_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    ensure_tasks_hours_column(db)
    db.commit()

    now = datetime.utcnow().isoformat()
    defaults = [
        ("admin", "admin123", "admin"),
        ("manager", "manager123", "manager"),
        ("member", "member123", "member"),
    ]
    for username, password, role in defaults:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, generate_password_hash(password), role, now),
            )

    default_clients = [
        ("KAMIKAZE Core", "Default client account"),
        ("Internal Operations", "Internal workstream"),
    ]
    for name, description in default_clients:
        cursor.execute("SELECT id FROM clients WHERE name = ?", (name,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO clients (name, description, created_at) VALUES (?, ?, ?)",
                (name, description, now),
            )

    db.commit()
    db.close()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            current_user = get_current_user()
            if current_user is None or current_user["role"] not in roles:
                flash("You are not authorized to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)

        return decorated

    return decorator


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


@app.context_processor
def inject_current_user():
    return {"current_user": get_current_user()}


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    current_user = get_current_user()
    db = get_db()

    if current_user["role"] in ["admin", "manager"]:
        summary = db.execute(
            """
            SELECT
                COUNT(*) AS total_tasks,
                SUM(CASE WHEN status = 'todo' THEN 1 ELSE 0 END) AS todo_count,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_count,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done_count,
                SUM(CASE WHEN date(due_date) < date('now') AND status != 'done' THEN 1 ELSE 0 END) AS overdue_count,
                COALESCE(SUM(hours_spent), 0) AS total_hours_spent
            FROM tasks
            """
        ).fetchone()

        tasks = db.execute(
            """
            SELECT t.*, c.name AS client_name,
                   u.username AS assignee_name,
                   a.username AS assigner_name
            FROM tasks t
            JOIN clients c ON c.id = t.client_id
            JOIN users u ON u.id = t.assigned_to
            JOIN users a ON a.id = t.assigned_by
            ORDER BY t.created_at DESC
            """
        ).fetchall()

        members = db.execute("SELECT id, username FROM users WHERE role = 'member' ORDER BY username").fetchall()
        clients = db.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
        attendance_records = db.execute(
            """
            SELECT at.*, u.username
            FROM attendance at
            JOIN users u ON u.id = at.user_id
            WHERE u.role IN ('member', 'manager')
            ORDER BY at.attendance_date DESC, u.username
            LIMIT 25
            """
        ).fetchall()

        return render_template(
            "dashboard_admin_manager.html",
            summary=summary,
            tasks=tasks,
            members=members,
            clients=clients,
            attendance_records=attendance_records,
        )

    tasks = db.execute(
        """
        SELECT t.*, c.name AS client_name, a.username AS assigner_name
        FROM tasks t
        JOIN clients c ON c.id = t.client_id
        JOIN users a ON a.id = t.assigned_by
        WHERE t.assigned_to = ?
        ORDER BY t.created_at DESC
        """,
        (current_user["id"],),
    ).fetchall()

    my_attendance = db.execute(
        """
        SELECT * FROM attendance
        WHERE user_id = ?
        ORDER BY attendance_date DESC
        LIMIT 15
        """,
        (current_user["id"],),
    ).fetchall()

    return render_template("dashboard_member.html", tasks=tasks, my_attendance=my_attendance)


@app.route("/members", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_members():
    db = get_db()
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("manage_members"))
        try:
            db.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'member', ?)",
                (username, generate_password_hash(password), datetime.utcnow().isoformat()),
            )
            db.commit()
            flash("Member created successfully.", "success")
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
        return redirect(url_for("manage_members"))

    members = db.execute("SELECT * FROM users WHERE role = 'member' ORDER BY created_at DESC").fetchall()
    return render_template("members.html", members=members)


@app.route("/members/<int:member_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_member(member_id):
    db = get_db()
    assigned_count = db.execute("SELECT COUNT(*) AS cnt FROM tasks WHERE assigned_to = ?", (member_id,)).fetchone()["cnt"]
    if assigned_count > 0:
        flash("Cannot delete member with assigned tasks.", "danger")
    else:
        db.execute("DELETE FROM users WHERE id = ? AND role = 'member'", (member_id,))
        db.commit()
        flash("Member deleted.", "success")
    return redirect(url_for("manage_members"))


@app.route("/members/<int:member_id>/reset-password", methods=["POST"])
@login_required
@role_required("admin")
def reset_password(member_id):
    new_password = request.form["new_password"].strip()
    if not new_password:
        flash("New password is required.", "danger")
        return redirect(url_for("manage_members"))
    db = get_db()
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ? AND role = 'member'",
        (generate_password_hash(new_password), member_id),
    )
    db.commit()
    flash("Password reset successfully.", "success")
    return redirect(url_for("manage_members"))


@app.route("/clients", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_clients():
    db = get_db()
    if request.method == "POST":
        name = request.form["name"].strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Client name is required.", "danger")
            return redirect(url_for("manage_clients"))
        try:
            db.execute(
                "INSERT INTO clients (name, description, created_at) VALUES (?, ?, ?)",
                (name, description, datetime.utcnow().isoformat()),
            )
            db.commit()
            flash("Client added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("Client already exists.", "danger")
        return redirect(url_for("manage_clients"))

    clients = db.execute("SELECT * FROM clients ORDER BY name").fetchall()
    return render_template("clients.html", clients=clients)


@app.route("/clients/<int:client_id>/update", methods=["POST"])
@login_required
@role_required("admin")
def update_client(client_id):
    name = request.form["name"].strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Client name is required.", "danger")
        return redirect(url_for("manage_clients"))

    db = get_db()
    try:
        db.execute("UPDATE clients SET name = ?, description = ? WHERE id = ?", (name, description, client_id))
        db.commit()
        flash("Client updated.", "success")
    except sqlite3.IntegrityError:
        flash("Client name already exists.", "danger")
    return redirect(url_for("manage_clients"))


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_client(client_id):
    db = get_db()
    used_count = db.execute("SELECT COUNT(*) AS cnt FROM tasks WHERE client_id = ?", (client_id,)).fetchone()["cnt"]
    if used_count > 0:
        flash("Cannot delete client linked to tasks.", "danger")
    else:
        db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        db.commit()
        flash("Client deleted.", "success")
    return redirect(url_for("manage_clients"))


@app.route("/tasks/create", methods=["POST"])
@login_required
@role_required("admin", "manager")
def create_task():
    db = get_db()
    title = request.form["title"].strip()
    description = request.form.get("description", "").strip()
    assigned_to = request.form["assigned_to"]
    client_id = request.form["client_id"]
    due_date = request.form["due_date"]

    if not title:
        flash("Task title is required.", "danger")
        return redirect(url_for("dashboard"))

    member = db.execute("SELECT id FROM users WHERE id = ? AND role = 'member'", (assigned_to,)).fetchone()
    client = db.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
    if member is None or client is None:
        flash("Invalid member/client selection.", "danger")
        return redirect(url_for("dashboard"))

    try:
        datetime.strptime(due_date, "%Y-%m-%d")
    except ValueError:
        flash("Due date format is invalid.", "danger")
        return redirect(url_for("dashboard"))

    today = date.today().isoformat()
    now = datetime.utcnow().isoformat()
    db.execute(
        """
        INSERT INTO tasks
            (title, description, status, client_id, assigned_to, assigned_by, allocated_date, due_date, hours_spent, created_at, updated_at)
        VALUES (?, ?, 'todo', ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (title, description, client_id, assigned_to, session["user_id"], today, due_date, now, now),
    )
    db.commit()
    flash("Task created successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/tasks/<int:task_id>/extend-due-date", methods=["POST"])
@login_required
@role_required("admin", "manager")
def extend_due_date(task_id):
    new_due_date = request.form["new_due_date"]
    try:
        datetime.strptime(new_due_date, "%Y-%m-%d")
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        "UPDATE tasks SET due_date = ?, updated_at = ? WHERE id = ?",
        (new_due_date, datetime.utcnow().isoformat(), task_id),
    )
    db.commit()
    flash("Due date updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/tasks/<int:task_id>/update", methods=["POST"])
@login_required
@role_required("member")
def update_task(task_id):
    db = get_db()
    current_user = get_current_user()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None or task["assigned_to"] != current_user["id"]:
        flash("Task not found or not assigned to you.", "danger")
        return redirect(url_for("dashboard"))

    status = request.form["status"]
    hours_spent = request.form.get("hours_spent", "0").strip() or "0"

    if status not in ["todo", "in_progress", "done"]:
        flash("Invalid status.", "danger")
        return redirect(url_for("dashboard"))

    try:
        hours_value = float(hours_spent)
        if hours_value < 0:
            raise ValueError
    except ValueError:
        flash("Hours must be a non-negative number.", "danger")
        return redirect(url_for("dashboard"))

    db.execute(
        "UPDATE tasks SET status = ?, hours_spent = ?, updated_at = ? WHERE id = ?",
        (status, hours_value, datetime.utcnow().isoformat(), task_id),
    )
    db.commit()
    flash("Task updated successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/attendance", methods=["POST"])
@login_required
@role_required("member", "manager")
def submit_attendance():
    current_user = get_current_user()
    attendance_date = request.form["attendance_date"]
    status = request.form["status"]
    remarks = request.form.get("remarks", "").strip()

    if status not in ["present", "absent", "half_day", "leave"]:
        flash("Invalid attendance status.", "danger")
        return redirect(url_for("dashboard"))

    try:
        datetime.strptime(attendance_date, "%Y-%m-%d")
    except ValueError:
        flash("Invalid attendance date.", "danger")
        return redirect(url_for("dashboard"))

    db = get_db()
    now = datetime.utcnow().isoformat()
    existing = db.execute(
        "SELECT id FROM attendance WHERE user_id = ? AND attendance_date = ?",
        (current_user["id"], attendance_date),
    ).fetchone()

    if existing:
        db.execute(
            "UPDATE attendance SET status = ?, remarks = ?, updated_at = ? WHERE id = ?",
            (status, remarks, now, existing["id"]),
        )
        flash("Attendance updated.", "success")
    else:
        db.execute(
            "INSERT INTO attendance (user_id, attendance_date, status, remarks, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (current_user["id"], attendance_date, status, remarks, now, now),
        )
        flash("Attendance submitted.", "success")

    db.commit()
    return redirect(url_for("dashboard"))


@app.route("/reports/task-logs")
@login_required
@role_required("admin", "manager")
def export_task_logs():
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    if not start_date or not end_date:
        flash("Start date and end date are required.", "danger")
        return redirect(url_for("dashboard"))

    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        flash("Invalid report date range.", "danger")
        return redirect(url_for("dashboard"))

    rows = get_db().execute(
        """
        SELECT date(t.updated_at) AS log_date,
               u.username AS member_name,
               c.name AS client_name,
               t.title AS task_title,
               t.allocated_date,
               t.due_date,
               t.hours_spent,
               t.status
        FROM tasks t
        JOIN users u ON u.id = t.assigned_to
        JOIN clients c ON c.id = t.client_id
        WHERE date(t.updated_at) BETWEEN date(?) AND date(?)
        ORDER BY t.updated_at DESC
        """,
        (start_date, end_date),
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Updated Date",
        "Member",
        "Client",
        "Task",
        "Allocated Date",
        "Due Date",
        "Hours Spent",
        "Status",
    ])
    for row in rows:
        writer.writerow(
            [
                row["log_date"],
                row["member_name"],
                row["client_name"],
                row["task_title"],
                row["allocated_date"],
                row["due_date"],
                row["hours_spent"],
                row["status"],
            ]
        )

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=task_logs_{start_date}_to_{end_date}.csv"
    return response


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
