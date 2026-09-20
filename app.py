from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import random

app = Flask(__name__)
app.secret_key = "secret123"

quotes = [
    "Stay consistent 🔥",
    "Discipline beats motivation 💪",
    "You are closer than you think 🚀",
    "Progress, not perfection, wins every day.",
    "Small steps every day lead to big goals.",
    "Study hard now, celebrate later.",
    "Your future self is already proud.",
    "Dream big, study smart, make it happen.",
    "Every minute counts—make it count.",
    "One more page, one more step forward."
]

# DATABASE
def init_db():
    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS subjects(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        name TEXT,
        difficulty INTEGER,
        exam_date TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS gamification(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT UNIQUE,
        points INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        badges TEXT DEFAULT '')""")

    cur.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_name TEXT,
        owner TEXT,
        participants TEXT,
        notes TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS resources(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        subject TEXT,
        resource_type TEXT,
        title TEXT,
        url TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS parent_access(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        child_user TEXT,
        parent_email TEXT,
        access_code TEXT)""")

    # Migration: add exam_date column if missing
    cur.execute("PRAGMA table_info(subjects)")
    columns = [row[1] for row in cur.fetchall()]
    if "exam_date" not in columns:
        cur.execute("ALTER TABLE subjects ADD COLUMN exam_date TEXT")

    cur.execute("""CREATE TABLE IF NOT EXISTS progress(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        task TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        subjects TEXT,
        exam_date TEXT)""")

    conn.commit()
    conn.close()

init_db()

# LOGIN
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("planner.db")
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            session["user"] = username
            return redirect("/dashboard")
        else:
            flash("Invalid login!")

    return render_template("login.html")


# SIGNUP
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password_raw = request.form["password"]
        confirm = request.form.get("confirm")

        if password_raw != confirm:
            flash("Passwords do not match!")
            return render_template("signup.html")

        password = generate_password_hash(password_raw)

        conn = sqlite3.connect("planner.db")
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users(username,password) VALUES (?,?)",
                        (username, password))
            cur.execute("INSERT INTO gamification(user,points,streak,badges) VALUES (?,?,?,?)",
                        (username, 0, 0, ""))
            conn.commit()
            flash("Account created!")
            return redirect("/")
        except sqlite3.IntegrityError:
            flash("Username already exists!")
        finally:
            conn.close()

    return render_template("signup.html")


# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ADD SUBJECT
@app.route("/add_subject", methods=["POST"])
def add_subject():
    if "user" not in session:
        return redirect("/")

    name = request.form["subject"].strip()
    diff = int(request.form["difficulty"])
    exam_date = request.form.get("exam_date", "")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO subjects(user,name,difficulty,exam_date) VALUES (?,?,?,?)",
                (session["user"], name, diff, exam_date))
    conn.commit()
    conn.close()

    return redirect("/dashboard")


# DELETE SUBJECT
@app.route("/delete_subject/<int:subject_id>")
def delete_subject(subject_id):
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM subjects WHERE id=? AND user=?", (subject_id, session["user"]))
    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/clear_subjects")
def clear_subjects():
    if "user" not in session:
        return redirect("/")
    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM subjects WHERE user=?", (session["user"],))
    cur.execute("DELETE FROM progress WHERE user=?", (session["user"],))
    conn.commit()
    conn.close()
    session.pop("timetable", None)
    session.pop("exam_date", None)
    session.pop("days_left", None)
    return redirect("/dashboard")


@app.route("/reset_progress")
def reset_progress():
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM progress WHERE user=?", (session["user"],))
    conn.commit()
    conn.close()
    return redirect("/dashboard")


@app.route("/create_session", methods=["POST"])
def create_session():
    if "user" not in session:
        return redirect("/")

    name = request.form.get("session_name", "Group Study")
    participants = request.form.get("participants", "")
    notes = request.form.get("notes", "")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO sessions(session_name, owner, participants, notes) VALUES (?, ?, ?, ?)",
                (name, session["user"], participants, notes))
    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/add_resource", methods=["POST"])
def add_resource():
    if "user" not in session:
        return redirect("/")

    subject = request.form.get("subject")
    resource_type = request.form.get("resource_type")
    title = request.form.get("title")
    url = request.form.get("url")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO resources(user,subject,resource_type,title,url) VALUES (?,?,?,?,?)",
                (session["user"], subject, resource_type, title, url))
    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/parent_portal", methods=["GET","POST"])
def parent_portal():
    message = None
    if request.method == "POST":
        child_user = request.form.get("child_user")
        parent_email = request.form.get("parent_email")
        access_code = request.form.get("access_code")

        conn = sqlite3.connect("planner.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO parent_access(child_user,parent_email,access_code) VALUES (?,?,?)",
                    (child_user, parent_email, access_code))
        conn.commit()
        conn.close()

        message = "Parent portal invitation recorded."

    return render_template("parent_portal.html", message=message)


# AI TIMETABLE
@app.route("/generate", methods=["POST"])
def generate():
    if "user" not in session:
        return redirect("/")

    exam_date = request.form.get("exam_date")

    if not exam_date:
        flash("Please select an exam date")
        return redirect("/dashboard")

    try:
        exam_obj = datetime.strptime(exam_date, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid exam date")
        return redirect("/dashboard")

    today = date.today()
    days_left = (exam_obj - today).days
    if days_left < 0:
        flash("Exam date must be today or in the future")
        return redirect("/dashboard")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, difficulty, exam_date FROM subjects WHERE user=?", (session["user"],))
    subject_rows = cur.fetchall()
    conn.close()

    if not subject_rows:
        flash("Add at least 1 subject before generating a plan")
        return redirect("/dashboard")

    def subject_score(row):
        _id, name, diff, s_date = row
        if s_date:
            try:
                due = (datetime.strptime(s_date, "%Y-%m-%d").date() - date.today()).days
            except ValueError:
                due = 999
        else:
            due = 999
        return (due, -diff)

    subjects_sorted = sorted(subject_rows, key=subject_score)

    task_list = []
    for _id, name, diff, s_date in subjects_sorted:
        weight = max(1, diff)
        task_list.extend([name] * weight)

    # Cap to available slots
    slots_per_day = 6
    total_slots = slots_per_day * max(days_left + 1, 1)
    if len(task_list) > total_slots:
        task_list = task_list[:total_slots]

    timetable = []
    for idx, sub in enumerate(task_list):
        day_offset = idx // slots_per_day
        hour = 9 + (idx % slots_per_day)
        plan_date = today + timedelta(days=day_offset)

        timetable.append({
            "time": f"{plan_date} {hour}:00",
            "task": f"Study {sub}"
        })

    session["timetable"] = timetable
    session["exam_date"] = exam_date
    session["days_left"] = days_left

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO history(user,subjects,exam_date) VALUES (?,?,?)",
                (session["user"], str([s[1] for s in subject_rows]), exam_date))
    conn.commit()
    conn.close()

    return redirect("/dashboard")


# MARK DONE
@app.route("/toggle_complete/<path:task>")
def toggle_complete(task):
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("SELECT id FROM progress WHERE user=? AND task=?", (session["user"], task))
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM progress WHERE id=?", (row[0],))
        delta_points = -5
        streak_change = 0
    else:
        cur.execute("INSERT INTO progress(user,task) VALUES (?,?)", (session["user"], task))
        delta_points = 15
        streak_change = 1

    cur.execute("SELECT points, streak FROM gamification WHERE user=?", (session["user"],))
    user_gam = cur.fetchone()
    if user_gam:
        points, streak = user_gam
        streak = max(streak + streak_change, 0)
        points = max(points + delta_points, 0)
        badge_list = []
        cur.execute("SELECT badges FROM gamification WHERE user=?", (session["user"],))
        badge_text = cur.fetchone()[0] or ""
        if points >= 100 and "Master Learner" not in badge_text:
            badge_list.append("Master Learner")
        if streak >= 7 and "7-Day Streak" not in badge_text:
            badge_list.append("7-Day Streak")
        if badge_list:
            badge_text = (badge_text + ", " + ", ".join(badge_list)).strip(', ')
        cur.execute("UPDATE gamification SET points=?, streak=?, badges=? WHERE user=?",
                    (points, streak, badge_text, session["user"]))
    conn.commit()
    conn.close()

    return redirect("/dashboard")


# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, difficulty, exam_date FROM subjects WHERE user=?", (session["user"],))
    subjects_rows = cur.fetchall()
    conn.close()

    subjects = []
    for r in subjects_rows:
        s_date = r[3] if len(r) > 3 else ""
        days_until = None
        if s_date:
            try:
                days_until = (datetime.strptime(s_date, "%Y-%m-%d").date() - date.today()).days
            except ValueError:
                days_until = None
        subjects.append({
            "id": r[0],
            "name": r[1],
            "difficulty": r[2],
            "exam_date": s_date,
            "days_until": days_until
        })
    timetable = session.get("timetable", [])

    # DAYS LEFT
    days_left = session.get("days_left")
    if days_left is None and "exam_date" in session:
        days_left = (datetime.strptime(session["exam_date"], "%Y-%m-%d") - datetime.today()).days

    # PROGRESS
    total = len(timetable)

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("SELECT task FROM progress WHERE user=?", (session["user"],))
    done_tasks = [row[0] for row in cur.fetchall()]
    done = len(done_tasks)
    conn.close()

    percent = (done / total * 100) if total > 0 else 0

    if percent >= 80:
        status = "Excellent 🚀"
    elif percent >= 50:
        status = "On Track 👍"
    else:
        status = "Needs Improvement"

    subject_progress = []
    weak_subjects = []
    for s in subjects:
        total_for_sub = s["difficulty"]
        done_for_sub = sum(1 for task in done_tasks if task == f"Study {s['name']}")
        sub_percent = (done_for_sub / total_for_sub * 100) if total_for_sub > 0 else 0
        bar_width = min(max(sub_percent, 0), 100)
        subject_progress.append({
            "name": s["name"],
            "done": done_for_sub,
            "total": total_for_sub,
            "percent": round(sub_percent, 2),
            "bar_width": round(bar_width, 2),
            "exam_date": s["exam_date"],
            "days_until": s.get("days_until")
        })
        if sub_percent < 60:
            weak_subjects.append(s["name"])

    recommendations = []
    if weak_subjects:
        recommendations.append(f"Focus extra time on weak subjects: {', '.join(weak_subjects)}")
    if days_left is not None and days_left <= 7:
        recommendations.append("Exam is close: prioritize high-difficulty subjects and avoid new topics.")
    elif days_left is not None and days_left <= 14:
        recommendations.append("Start daily focused blocks on near-term exam subjects.")
    else:
        recommendations.append("Great time to build habit: review weak topics and expand depth.")

    notifications = []
    popup_notifications = []
    if days_left is not None and days_left <= 3:
        notifications.append("Reminder: exam is within 3 days — finalize your plan now.")
        popup_notifications.append("Reminder: exam is within 3 days — finalize your plan now.")
    if len(done_tasks) < 1 and subjects_rows:
        popup_notifications.append("No tasks completed yet — begin with a first study block.")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("SELECT points, streak, badges FROM gamification WHERE user=?", (session["user"],))
    gam = cur.fetchone() or (0,0,"")
    conn.close()

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("SELECT id, session_name, owner, participants FROM sessions ORDER BY id DESC LIMIT 3")
    group_sessions = cur.fetchall()

    cur.execute("SELECT id, subject, resource_type, title, url FROM resources WHERE user=?", (session["user"],))
    resources = cur.fetchall()
    conn.close()

    subject_names = [s["name"].lower() for s in subjects]
    suggested_channels = [
        {"name": "Khan Academy", "url": "https://www.khanacademy.org", "notes": "Free video lessons"},
        {"name": "Coursera", "url": "https://www.coursera.org", "notes": "Courses from top universities"},
        {"name": "edX", "url": "https://www.edx.org", "notes": "Professional certificate courses"},
        {"name": "Quizlet", "url": "https://quizlet.com", "notes": "Flashcards and practice tests"},
        {"name": "YouTube Education", "url": "https://www.youtube.com/education", "notes": "Video tutorials"}
    ]

    if any("math" in subj for subj in subject_names):
        suggested_channels.append({"name": "PatrickJMT", "url": "https://www.youtube.com/user/patrickJMT", "notes": "Math walkthroughs"})
    if any(x in subj for subj in subject_names for x in ["python", "programming", "code"]):
        suggested_channels.append({"name": "Corey Schafer", "url": "https://www.youtube.com/user/schafer5", "notes": "Python tutorials"})
    if any(x in subj for subj in subject_names for x in ["physics", "chemistry"]):
        suggested_channels.append({"name": "CrashCourse", "url": "https://www.youtube.com/user/crashcourse", "notes": "Quick conceptual videos"})

    # AI exam predictor, simple linear baseline
    predicted_score = min(100, max(0, round(percent * 0.85 + (100 - days_left if days_left else 0) * 0.1))) if days_left is not None else round(percent)

    return render_template("dashboard.html",
                           subjects=subjects,
                           timetable=timetable,
                           percent=round(percent,2),
                           status=status,
                           days_left=days_left,
                           quote=random.choice(quotes),
                           done_tasks=done_tasks,
                           subject_progress=subject_progress,
                           recommendations=recommendations,
                           notifications=notifications,
                           popup_notifications=popup_notifications,
                           suggested_channels=suggested_channels,
                           gamification={"points": gam[0], "streak": gam[1], "badges": gam[2]},
                           group_sessions=group_sessions,
                           resources=resources,
                           predicted_score=predicted_score)


# HISTORY
@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("SELECT id, subjects, exam_date FROM history WHERE user=?",
                (session["user"],))
    data = cur.fetchall()
    conn.close()

    return render_template("history.html", data=data)


@app.route("/export_data")
def export_data():
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, difficulty, exam_date FROM subjects WHERE user=?", (session["user"],))
    subjects = cur.fetchall()
    cur.execute("SELECT task FROM progress WHERE user=?", (session["user"],))
    progress = cur.fetchall()
    cur.execute("SELECT id, subject, resource_type, title, url FROM resources WHERE user=?", (session["user"],))
    resources = cur.fetchall()
    conn.close()

    export_json = {
        "subjects": [dict(id=r[0], name=r[1], difficulty=r[2], exam_date=r[3]) for r in subjects],
        "progress": [p[0] for p in progress],
        "resources": [dict(id=r[0], subject=r[1], resource_type=r[2], title=r[3], url=r[4]) for r in resources]
    }

    from flask import make_response
    import json
    data = json.dumps(export_json, indent=2)
    response = make_response(data)
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = "attachment; filename=study_planner_export.json"
    return response


@app.route("/delete_resource/<int:resource_id>")
def delete_resource(resource_id):
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM resources WHERE id=? AND user=?", (resource_id, session["user"]))
    conn.commit()
    conn.close()
    return redirect("/dashboard")


@app.route("/delete_session/<int:session_id>")
def delete_session(session_id):
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE id=? AND owner=?", (session_id, session["user"]))
    conn.commit()
    conn.close()
    return redirect("/dashboard")


@app.route("/delete_history/<int:history_id>")
def delete_history(history_id):
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("planner.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM history WHERE id=? AND user=?", (history_id, session["user"]))
    conn.commit()
    conn.close()

    return redirect("/history")


if __name__ == "__main__":
    app.run(debug=True)