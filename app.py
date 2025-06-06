import smtplib
from email.message import EmailMessage
from config import EMAIL_ADDRESS, EMAIL_PASSWORD

from flask import Flask, render_template, request, redirect, url_for, session, Response, flash, send_file, g
import sqlite3
from slot_allocator import assign_slots
from datetime import timedelta, datetime
import time
import csv
from database import get_db
from io import StringIO, BytesIO, TextIOWrapper 
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'secure_exam_key'
app.permanent_session_lifetime = timedelta(minutes=5)

@app.route('/')
def index():
    return render_template('student_index.html')

@app.route('/student_login')
def student_login():
    return render_template('student_login.html')

@app.route('/login', methods=['POST'])
def login():
    matric = request.form['matric']
    dept = request.form['department']
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT OR IGNORE INTO students (matric, department) VALUES (?, ?)", (matric, dept))
    db.commit()
    cursor.execute("SELECT slot, course_code FROM students WHERE matric = ?", (matric,))
    result = cursor.fetchone()
    slot = result['slot'] if result else None
    course_code = result['course_code'] if result else "N/A"

    if slot:
        cursor.execute("SELECT start_time, end_time FROM slot_times WHERE slot = ?", (slot,))
        time = cursor.fetchone()
        start_time = time['start_time'] if time else "N/A"
        end_time = time['end_time'] if time else "N/A"
    else:
        start_time = end_time = "Not assigned"

    session['matric'] = matric
    session['slot'] = slot
    session['start'] = start_time
    session['end'] = end_time
    session['course_code'] = course_code
    return redirect(url_for('student_slot'))

@app.route('/student_slot')
def student_slot():
    if 'matric' not in session:
        return redirect(url_for('index'))
    return render_template('student_slot.html',
                           slot=session['slot'],
                           start=session['start'],
                           end=session['end'],
                           matric=session['matric'],
                           course_code=session.get('course_code', 'N/A'))


# --- Student Logout Route ---
@app.route('/student_logout')
def student_logout():
    session_keys = ['matric', 'slot', 'start', 'end', 'course_code']
    for key in session_keys:
        session.pop(key, None)
    flash('You have been logged out successfully.')
    return redirect(url_for('student_login'))


# --- Admin Logout Route (already in your code, but make sure it's correct) ---
@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Admin logged out successfully.')
    return redirect(url_for('admin_login'))


@app.before_first_request
def initialize_reschedule_table():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reschedule_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matric TEXT NOT NULL,
            reason TEXT NOT NULL,
            requested_slot TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()

@app.route('/admin_reschedules')
def admin_reschedules():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM reschedule_requests WHERE status = 'Pending'")
    requests = cursor.fetchall()
    return render_template('admin_reschedule_view.html', requests=requests)

@app.route('/admin_reschedule_action', methods=['POST'])
def admin_reschedule_action():
    request_id = request.form['id']
    matric = request.form['matric']
    slot = request.form['slot']
    action = request.form['action']

    db = get_db()
    cursor = db.cursor()

    if action == 'approve':
        cursor.execute("UPDATE students SET slot = ? WHERE matric = ?", (slot, matric))
        cursor.execute("UPDATE reschedule_requests SET status = 'Approved' WHERE id = ?", (request_id,))
        flash(f"Approved and updated slot for {matric} to Slot {slot}.")
    elif action == 'decline':
        cursor.execute("UPDATE reschedule_requests SET status = 'Declined' WHERE id = ?", (request_id,))
        flash(f"Declined reschedule request for {matric}.")

    db.commit()
    return redirect(url_for('admin_reschedules'))



@app.before_request
def make_session_permanent():
    session.permanent = True
    session.modified = True
    if 'last_activity' in session:
        now = time.time()
        if now - session['last_activity'] > 300:
            session.clear()
            flash('Session expired. Please log in again.')
            return redirect(url_for('login'))
    session['last_activity'] = time.time()

# (Rest of the file remains unchanged)

def send_email(recipient, subject, content):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient
    msg.set_content(content)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print("Failed to send email:", e)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('database.db')
        db.row_factory = sqlite3.Row
    return db














@app.route('/request_reschedule', methods=['GET', 'POST'])
def request_reschedule():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        matric = request.form['matric']
        reason = request.form['reason']
        requested_slot = request.form['requested_slot']

        # Check if there's already a pending reschedule request
        cursor.execute("SELECT * FROM reschedule_requests WHERE matric = ? AND status = 'Pending'", (matric,))
        existing_request = cursor.fetchone()

        if existing_request:
            flash("You have already submitted a reschedule request. Please wait for admin approval or cancel it.")
        else:
            cursor.execute("INSERT INTO reschedule_requests (matric, reason, requested_slot) VALUES (?, ?, ?)",
                           (matric, reason, requested_slot))
            db.commit()
            flash("Reschedule request submitted successfully.")

        return redirect(url_for('request_reschedule'))

    # For GET, show the reschedule request form and any existing request
    existing = None
    if 'matric' in session:
        cursor.execute("SELECT * FROM reschedule_requests WHERE matric = ? AND status = 'Pending'", (session['matric'],))
        existing = cursor.fetchone()

    return render_template('request_reschedule.html', existing_request=existing)


@app.route('/cancel_reschedule/<int:request_id>', methods=['POST'])
def cancel_reschedule(request_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM reschedule_requests WHERE id = ? AND status = 'Pending'", (request_id,))
    db.commit()
    flash("Reschedule request cancelled.")
    return redirect(url_for('request_reschedule'))



@app.route('/send_emails', methods=['GET'])
def send_emails():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT matric, department, level, slot FROM students")
    students = cursor.fetchall()
    for student in students:
        matric = student['matric']
        department = student['department']
        level = student['level']
        slot = student['slot']
        cursor.execute("SELECT start_time, end_time FROM slot_times WHERE slot = ?", (slot,))
        slot_time = cursor.fetchone()
        start_time = slot_time['start_time'] if slot_time else "Unknown"
        end_time = slot_time['end_time'] if slot_time else "Unknown"
        subject = "Exam Slot Notification"
        content = f"""Hello {matric},\n\nYou have been scheduled for your Computer-Based Exam.\n\nSlot: {slot}\nTime: {start_time} to {end_time}\nDepartment: {department}\nLevel: {level}\n\nPlease be punctual."""
        send_email(matric + "@example.com", subject, content)
    flash("Emails have been sent to all students.")
    return redirect(url_for('admin'))



@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()



@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html')



def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.before_request
def require_login():
    protected_routes = ['/admin', '/upload', '/export', '/reassign']
    exempt_routes = ['/admin_login', '/logout', '/static', '/']
    if any(request.path.startswith(route) for route in protected_routes):
        if request.path not in exempt_routes and 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))

@app.route('/admin')
def admin():
    db = get_db()  # <-- Make sure this line exists
    cursor = db.cursor()
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    cursor.execute("SELECT slot, COUNT(*) as count FROM students GROUP BY slot ORDER BY slot ASC")
    stats = cursor.fetchall()
    slot_labels = [str(row['slot']) for row in stats]
    slot_counts = [row['count'] for row in stats]
    return render_template('admin.html', students=students, slot_labels=slot_labels, slot_counts=slot_counts)

@app.route('/reassign', methods=['POST'])
def reassign():
    matric = request.form['matric']
    new_slot = request.form['new_slot']
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE students SET slot = ? WHERE matric = ?", (new_slot, matric))
    db.commit()
    cursor.execute("SELECT matric, department, level, slot FROM students")
    students = cursor.fetchall()
    for student in students:
        student_matric = student['matric']
        department = student['department']
        level = student['level']
        slot = student['slot']
        cursor.execute("SELECT start_time, end_time FROM slot_times WHERE slot = ?", (slot,))
        slot_time = cursor.fetchone()
        start_time = slot_time['start_time'] if slot_time else "Unknown"
        end_time = slot_time['end_time'] if slot_time else "Unknown"
        subject = "Updated Exam Slot Assignment"
        content = f"""Hello {student_matric},\n\nYou have been scheduled for your Computer-Based Exam.\n\nSlot: {slot}\nTime: {start_time} to {end_time}\nDepartment: {department}\nLevel: {level}\n\nPlease be punctual."""
        send_email(student_matric + "@example.com", subject, content)
    return redirect(url_for('admin'))

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    stream = TextIOWrapper(file.stream)
    reader = csv.DictReader(stream)
    students = []
    db = get_db()
    cursor = db.cursor()
    for row in reader:
        matric = row['matric']
        department = row['department']
        level = row['level']
        cursor.execute("SELECT slot FROM students WHERE matric = ?", (matric,))
        existing = cursor.fetchone()
        if not existing or not existing['slot']:
            students.append({'matric': matric, 'department': department, 'level': level})
    cursor.execute("SELECT MAX(CAST(slot AS INTEGER)) as max_slot FROM students")
    result = cursor.fetchone()
    last_slot = result['max_slot'] if result['max_slot'] else 0
    start_slot = last_slot + 1
    grouped = assign_slots(students, start_slot=start_slot)
    for slot, group in grouped.items():
        for s in group:
            cursor.execute("INSERT OR REPLACE INTO students (matric, department, level, slot) VALUES (?, ?, ?, ?)",
                           (s['matric'], s['department'], s['level'], str(slot)))
    db.commit()
    return redirect(url_for('admin'))

@app.route('/export')
def export():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT s.matric, s.department, s.level, s.slot, t.start_time, t.end_time
        FROM students s
        LEFT JOIN slot_times t ON s.slot = t.slot
        ORDER BY s.slot ASC
    ''')
    rows = cursor.fetchall()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Matric', 'Department', 'Level', 'Slot', 'Start Time', 'End Time'])
    for row in rows:
        writer.writerow([row['matric'], row['department'], row['level'], row['slot'], row['start_time'], row['end_time']])
    output.seek(0)
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=exam_schedule.csv"})

@app.route('/export_pdf')
def export_pdf():
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "Exam Slot Allocation Report")
    p.setFont("Helvetica", 10)
    p.drawString(50, height - 65, "Generated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    p.setFont("Helvetica-Bold", 12)
    headers = ["Matric", "Department", "Level", "Slot", "Start Time", "End Time"]
    x_positions = [50, 120, 250, 310, 370, 440]
    for i, header in enumerate(headers):
        p.drawString(x_positions[i], height - 90, header)
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT s.matric, s.department, s.level, s.slot, t.start_time, t.end_time
        FROM students s
        LEFT JOIN slot_times t ON s.slot = t.slot
        ORDER BY s.slot ASC
    ''')
    rows = cursor.fetchall()
    y = height - 110
    p.setFont("Helvetica", 10)
    for row in rows:
        if y < 40:
            p.showPage()
            y = height - 50
        p.drawString(x_positions[0], y, row['matric'])
        p.drawString(x_positions[1], y, row['department'])
        p.drawString(x_positions[2], y, str(row['level']))
        p.drawString(x_positions[3], y, str(row['slot']))
        p.drawString(x_positions[4], y, row['start_time'] or "")
        p.drawString(x_positions[5], y, row['end_time'] or "")
        y -= 15
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="exam_schedule.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS students (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        matric TEXT UNIQUE,
                        department TEXT,
                        level TEXT,
                        slot TEXT)''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS slot_times (
            slot INTEGER PRIMARY KEY,
            start_time TEXT,
            end_time TEXT
        )
    ''')
    for i in range(10):
        start_hour = 9 + i
        cursor.execute("INSERT OR IGNORE INTO slot_times (slot, start_time, end_time) VALUES (?, ?, ?)",
                       (i+1, f"{start_hour:02}:00", f"{start_hour+1:02}:00"))
    conn.commit()
    conn.close()
    app.run(debug=True)
