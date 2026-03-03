import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, g, redirect, render_template, request, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "task_manager.db")

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
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL CHECK(status IN ('todo', 'in_progress', 'done')) DEFAULT 'todo',
            assigned_to INTEGER NOT NULL,
            assigned_by INTEGER NOT NULL,
            hours_allocated REAL DEFAULT 0,
            hours_spent REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (assigned_to) REFERENCES users(id),
            FOREIGN KEY (assigned_by) REFERENCES users(id)
        )
        """
    )

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
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


@app.context_processor
def inject_current_user():
    return {"current_user": get_current_user()}


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    current_user = get_current_user()

    if current_user["role"] in ["admin", "manager"]:
        summary = db.execute(
            """
            SELECT
                COUNT(*) AS total_tasks,
                SUM(CASE WHEN status = 'todo' THEN 1 ELSE 0 END) AS todo_count,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_count,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done_count,
                COALESCE(SUM(hours_allocated), 0) AS total_allocated,
                COALESCE(SUM(hours_spent), 0) AS total_spent
            FROM tasks
            """
        ).fetchone()

        tasks = db.execute(
            """
            SELECT t.*, u.username AS assignee_name, a.username AS assigner_name
            FROM tasks t
            JOIN users u ON t.assigned_to = u.id
            JOIN users a ON t.assigned_by = a.id
            ORDER BY t.created_at DESC
            """
        ).fetchall()

        members = db.execute("SELECT id, username FROM users WHERE role = 'member' ORDER BY username").fetchall()

        return render_template(
            "dashboard_admin_manager.html",
            summary=summary,
            tasks=tasks,
            members=members,
        )

    tasks = db.execute(
        """
        SELECT t.*, a.username AS assigner_name
        FROM tasks t
        JOIN users a ON t.assigned_by = a.id
        WHERE t.assigned_to = ?
        ORDER BY t.created_at DESC
        """,
        (current_user["id"],),
    ).fetchall()
    return render_template("dashboard_member.html", tasks=tasks)


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

    task_count = db.execute("SELECT COUNT(*) AS cnt FROM tasks WHERE assigned_to = ?", (member_id,)).fetchone()["cnt"]
    if task_count > 0:
        flash("Cannot delete member with assigned tasks. Reassign tasks first.", "danger")
        return redirect(url_for("manage_members"))

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
        flash("New password cannot be empty.", "danger")
        return redirect(url_for("manage_members"))

    db = get_db()
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ? AND role = 'member'",
        (generate_password_hash(new_password), member_id),
    )
    db.commit()
    flash("Password reset successfully.", "success")
    return redirect(url_for("manage_members"))


@app.route("/tasks/create", methods=["POST"])
@login_required
@role_required("admin", "manager")
def create_task():
    db = get_db()
    title = request.form["title"].strip()
    description = request.form["description"].strip()
    assigned_to = request.form["assigned_to"]
    hours_allocated = request.form.get("hours_allocated", "0").strip() or "0"

    if not title:
        flash("Task title is required.", "danger")
        return redirect(url_for("dashboard"))

    try:
        hours_allocated_value = float(hours_allocated)
        if hours_allocated_value < 0:
            raise ValueError
    except ValueError:
        flash("Allocated hours must be a non-negative number.", "danger")
        return redirect(url_for("dashboard"))

    member = db.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'member'", (assigned_to,)
    ).fetchone()

    if member is None:
        flash("Invalid member selected.", "danger")
        return redirect(url_for("dashboard"))

    now = datetime.utcnow().isoformat()
    db.execute(
        """
        INSERT INTO tasks (title, description, status, assigned_to, assigned_by, hours_allocated, hours_spent, created_at, updated_at)
        VALUES (?, ?, 'todo', ?, ?, ?, 0, ?, ?)
        """,
        (title, description, assigned_to, session["user_id"], hours_allocated_value, now, now),
    )
    db.commit()
    flash("Task created and assigned successfully.", "success")
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
        hours_spent_value = float(hours_spent)
        if hours_spent_value < 0:
            raise ValueError
    except ValueError:
        flash("Hours spent must be a non-negative number.", "danger")
        return redirect(url_for("dashboard"))

    db.execute(
        "UPDATE tasks SET status = ?, hours_spent = ?, updated_at = ? WHERE id = ?",
        (status, hours_spent_value, datetime.utcnow().isoformat(), task_id),
    )
    db.commit()
    flash("Task updated successfully.", "success")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
