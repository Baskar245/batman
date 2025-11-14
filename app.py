from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'attendance_secret'

# ---------- AIVEN DATABASE CONFIG ----------
DB_CONFIG = {
    'host': 'pg-1b34e6ac-newtonbaskar04-b16.f.aivencloud.com',
    'port': 28539,
    'database': 'defaultdb',
    'user': 'avnadmin',
    'password': 'AVNS_SKaC_IhYxTQIgIVJPfl',
    'sslmode': 'require'
}

# ---------- DATABASE SETUP ----------
def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE,
                    password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS classes (
                    id SERIAL PRIMARY KEY,
                    department TEXT,
                    year TEXT,
                    subject TEXT,
                    num_students INTEGER,
                    created_by TEXT)''')   # 🆕 Added created_by
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    class_id INTEGER,
                    regno TEXT,
                    name TEXT,
                    created_by TEXT)''')   # 🆕 Added created_by
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id SERIAL PRIMARY KEY,
                    class_id INTEGER,
                    student_id INTEGER,
                    date TEXT,
                    status TEXT,
                    created_by TEXT)''')   # 🆕 Added created_by
    conn.commit()
    conn.close()

# helper for new DB connection
def get_conn():
    return psycopg2.connect(**DB_CONFIG)

# ---------- HOME / LOGIN / REGISTER ----------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username'].strip()
        pwd = request.form['password'].strip()
        if not uname or not pwd:
            return "Provide username and password."
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (%s,%s)", (uname, pwd))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except psycopg2.Error:
            conn.close()
            return "Username already exists!"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username'].strip()
        pwd = request.form['password'].strip()
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=%s AND password=%s", (uname, pwd))
        user = c.fetchone()
        conn.close()
        if user:
            session['username'] = uname
            return redirect(url_for('dashboard', username=uname))
        else:
            return "Invalid username or password!"
    return render_template('login.html')

# ---------- DASHBOARD ----------
@app.route('/dashboard/<username>')
def dashboard(username):
    conn = get_conn()
    cur = conn.cursor()
    # 🆕 Show only classes created by logged-in user
    cur.execute("SELECT * FROM classes WHERE created_by=%s", (username,))
    classes = cur.fetchall()
    conn.close()
    return render_template('dashboard.html', username=username, classes=classes)

# ---------- CREATE CLASS ----------
@app.route('/create_class/<username>', methods=['GET', 'POST'])
def create_class(username):
    if request.method == 'POST':
        dept = request.form.get('department', '').strip()
        year = request.form.get('year', '').strip()
        subject = request.form.get('subject', '').strip()
        num_students = request.form.get('num_students') or request.form.get('total_students') or 0
        try:
            num_students = int(num_students)
        except:
            num_students = 0
        conn = get_conn()
        cur = conn.cursor()
        # 🆕 Include created_by (username)
        cur.execute("INSERT INTO classes (department, year, subject, num_students, created_by) VALUES (%s,%s,%s,%s,%s)",
                    (dept, year, subject, num_students, username))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard', username=username))
    return render_template('create_class.html', username=username)

# ---------- SAVE CLASS ----------
@app.route('/save_class', methods=['POST'])
@app.route('/save_class/<username>', methods=['POST'])
def save_class(username=None):
    if not username:
        username = request.form.get('username') or session.get('username')
    department = request.form.get('department', '').strip()
    year = request.form.get('year', '').strip()
    subject = request.form.get('subject', '').strip()
    num_students = request.form.get('num_students') or request.form.get('total_students') or 0
    try:
        num_students = int(num_students)
    except:
        num_students = 0
    conn = get_conn()
    cur = conn.cursor()
    # 🆕 Include created_by field
    cur.execute("INSERT INTO classes (department, year, subject, num_students, created_by) VALUES (%s,%s,%s,%s,%s)",
                (department, year, subject, num_students, username))
    conn.commit()
    conn.close()
    if username:
        return redirect(url_for('dashboard', username=username))
    return redirect(url_for('login'))

# ---------- STUDENT ENTRY ----------
@app.route('/student_entry/<int:class_id>', methods=['GET', 'POST'])
def student_entry(class_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT num_students, department, year, subject, created_by FROM classes WHERE id=%s", (class_id,))
    cls = cur.fetchone()
    if not cls:
        conn.close()
        return "Class not found."
    num_students = cls[0] or 0
    dept, year, subj, created_by = cls[1], cls[2], cls[3], cls[4]
    if request.method == 'POST':
        students = []
        for i in range(num_students):
            regno = request.form.get(f"regno{i}")
            name = request.form.get(f"name{i}")
            if regno and name:
                # 🆕 Add created_by
                students.append((class_id, regno.strip(), name.strip(), session.get('username')))
        if students:
            cur.executemany("INSERT INTO students (class_id, regno, name, created_by) VALUES (%s,%s,%s,%s)", students)
            conn.commit()
        conn.close()
        return redirect(url_for('dashboard', username=session.get('username', '')))
    conn.close()
    return render_template('student_entry.html', class_id=class_id, dept=dept, year=year, subj=subj, num_students=num_students)

# ---------- TAKE ATTENDANCE ----------
@app.route('/take_attendance')
@app.route('/take_attendance/<username>')
def take_attendance(username=None):
    if not username:
        username = session.get('username')
    conn = get_conn()
    cur = conn.cursor()
    # 🆕 Show only classes of logged-in user
    cur.execute("SELECT * FROM classes WHERE created_by=%s", (username,))
    classes = cur.fetchall()
    conn.close()
    return render_template('attendance_select.html', username=username, classes=classes)

# ---------- ATTENDANCE TABLE ----------
@app.route('/attendance_table/<int:class_id>', methods=['GET', 'POST'])
def attendance_table(class_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, regno, name FROM students WHERE class_id=%s", (class_id,))
    students = cur.fetchall()
    cur.execute("SELECT department, year, subject, created_by FROM classes WHERE id=%s", (class_id,))
    class_info = cur.fetchone()
    if not class_info:
        conn.close()
        return "Class not found."
    if request.method == 'POST':
        mode = request.form.get('mode') or 'auto'
        if mode == 'manual':
            manual_date = request.form.get('manual_date')
            manual_time = request.form.get('manual_time')
            if manual_date and manual_time:
                try:
                    date = f"{manual_date} {manual_time}:00"
                except:
                    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        attendance_records = []
        for student in students:
            status = request.form.get(f"status_{student[0]}", "A")
            # 🆕 Include created_by
            attendance_records.append((class_id, student[0], date, status, session.get('username')))
        if attendance_records:
            cur.executemany("INSERT INTO attendance (class_id, student_id, date, status, created_by) VALUES (%s,%s,%s,%s,%s)", attendance_records)
            conn.commit()
        conn.close()
        return redirect(url_for('attendance_table', class_id=class_id))
    cur.execute("SELECT student_id, date, status FROM attendance WHERE class_id=%s", (class_id,))
    all_attendance = cur.fetchall()
    attendance_dict = {}
    for sid, date, status in all_attendance:
        if sid not in attendance_dict:
            attendance_dict[sid] = {}
        attendance_dict[sid][date] = status
    all_dates = sorted(set([record[1].split(" ")[0] for record in all_attendance]))
    total_classes = len(all_dates)
    stats = {}
    for student in students:
        sid = student[0]
        student_attendance = attendance_dict.get(sid, {})
        present_count = sum(1 for d in student_attendance.values() if d == "P")
        percentage = (present_count / total_classes * 100) if total_classes > 0 else 0
        stats[sid] = {"present": present_count, "total": total_classes, "percent": round(percentage, 2)}
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    conn.close()
    return render_template('attendance_table.html',
                           students=students,
                           class_info=class_info,
                           class_id=class_id,
                           attendance_dict=attendance_dict,
                           all_dates=all_dates,
                           stats=stats,
                           current_date=current_date,
                           current_time=current_time)

# ---------- ATTENDANCE CALCULATION ----------
@app.route('/attendance_calculation/<int:class_id>', methods=['GET', 'POST'])
def attendance_calculation(class_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT department, year, subject, id FROM classes WHERE id=%s", (class_id,))
    class_info = cur.fetchone()
    if not class_info:
        conn.close()
        return "Class not found."
    message = None
    query = """
        SELECT s.id, s.regno, s.name, a.status, a.date
        FROM students s
        JOIN attendance a ON s.id = a.student_id
        WHERE s.class_id=%s
    """
    params = [class_id]
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'single':
            single_date = request.form.get('single_date')
            if single_date:
                query += " AND DATE(a.date)=%s"
                params.append(single_date)
            else:
                message = "Please select a date."
        elif action == 'range':
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            if start_date and end_date:
                query += " AND DATE(a.date) BETWEEN %s AND %s"
                params.extend([start_date, end_date])
            else:
                message = "Please select both start and end dates."
    cur.execute(query, params)
    data = cur.fetchall()
    stats_dict = {}
    for sid, regno, name, status, date in data:
        if sid not in stats_dict:
            stats_dict[sid] = {"regno": regno, "name": name, "present": 0, "total": 0}
        stats_dict[sid]["total"] += 1
        if status == "P":
            stats_dict[sid]["present"] += 1
    students_summary = []
    for sid, s in stats_dict.items():
        percent = round((s["present"] / s["total"]) * 100, 2) if s["total"] > 0 else 0
        students_summary.append({
            "id": sid,
            "regno": s["regno"],
            "name": s["name"],
            "present": s["present"],
            "total": s["total"],
            "percent": percent
        })
    conn.close()
    return render_template('attendance_calculation.html',
                           class_info=class_info,
                           students=students_summary,
                           stats=stats_dict,
                           message=message)

# ---------- MAIN ----------
if __name__ == '__main__':
    init_db()  # optional, only if your tables may not exist
  
    port = int(os.environ.get("PORT", 5000))  # Render assigns a PORT
    app.run(host="0.0.0.0", port=port, debug=True)

