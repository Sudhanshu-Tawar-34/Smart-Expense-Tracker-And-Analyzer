from flask import Flask, render_template, request, redirect, session, Response, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")


# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        category TEXT,
        date TEXT,
        note TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        source TEXT,
        date TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        target REAL
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS budget (
        user_id INTEGER PRIMARY KEY,
        amount REAL
    )
    ''')

    conn.commit()
    conn.close()


init_db()


# ---------------- HELPERS ----------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/')
        return f(*args, **kwargs)
    return wrapper


def get_user_id():
    return session.get('user_id')


def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0


# ---------------- AUTH ----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db()
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (request.form['username'],))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            return redirect('/dashboard')

        flash("Invalid credentials ❌")
        return redirect('/')

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            return render_template('signup.html', error="Passwords mismatch ❌")

        conn = get_db()
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (username,))
        if c.fetchone():
            return render_template('signup.html', error="Username exists ❌")

        hashed = generate_password_hash(password)

        c.execute("INSERT INTO users (username, password) VALUES (?,?)", (username, hashed))

        conn.commit()
        conn.close()

        flash("Account created successfully ✅")
        return redirect('/')

    return render_template('signup.html')


@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Logged out successfully 👋")
    return redirect('/')


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
@login_required
def dashboard():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?", (user_id,))
    total = safe_float(c.fetchone()[0])

    c.execute("SELECT SUM(amount) FROM income WHERE user_id=?", (user_id,))
    income = safe_float(c.fetchone()[0])

    balance = income - total
    savings_rate = (balance / income * 100) if income > 0 else 0

    c.execute("SELECT * FROM expenses WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,))
    recent = c.fetchall()

    c.execute("SELECT name, target FROM goals WHERE user_id=?", (user_id,))
    goals = c.fetchall()

    c.execute("SELECT amount FROM budget WHERE user_id=?", (user_id,))
    row = c.fetchone()
    budget = safe_float(row['amount']) if row else 0

    # alerts
    alerts = []
    if balance < 0:
        alerts.append("⚠️ You are overspending!")
    if budget and total > budget:
        alerts.append("⚠️ Budget exceeded!")
    if savings_rate < 20:
        alerts.append("⚠️ Low savings rate!")

    conn.close()

    return render_template('dashboard.html',
                           total=total,
                           recent=recent,
                           income=income,
                           balance=balance,
                           savings_rate=savings_rate,
                           goals=goals,
                           alerts=alerts,
                           budget=budget)


# ---------------- ADD EXPENSE ----------------
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        user_id = get_user_id()

        amount = safe_float(request.form.get('amount'))
        category = request.form.get('category')
        custom = request.form.get('custom_category')

        if category == "Others" and custom:
            category = custom

        if amount <= 0 or not category:
            flash("Invalid input ❌")
            return redirect('/add')

        conn = get_db()
        c = conn.cursor()

        c.execute("""
        INSERT INTO expenses (user_id, amount, category, date, note)
        VALUES (?,?,?,?,?)
        """, (user_id, amount,
              category,
              request.form.get('date'),
              request.form.get('note')))

        conn.commit()
        conn.close()

        flash("Expense added ✅")
        return redirect('/history')

    return render_template('add_expense.html')


# ---------------- ADD INCOME ----------------
@app.route('/add_income', methods=['GET', 'POST'])
@login_required
def add_income():
    if request.method == 'POST':
        amount = safe_float(request.form['amount'])

        if amount <= 0:
            flash("Invalid amount ❌")
            return redirect('/add_income')

        conn = get_db()
        c = conn.cursor()

        c.execute("""
        INSERT INTO income (user_id, amount, source, date)
        VALUES (?,?,?,?)
        """, (get_user_id(), amount,
              request.form['source'],
              request.form['date']))

        conn.commit()
        conn.close()

        flash("Income added 💰")
        return redirect('/history')

    return render_template('add_income.html')


# ---------------- ADD GOAL ----------------
@app.route('/add_goal', methods=['GET', 'POST'])
@login_required
def add_goal():
    if request.method == 'POST':
        target = safe_float(request.form['target'])

        if target <= 0:
            flash("Invalid goal ❌")
            return redirect('/add_goal')

        conn = get_db()
        c = conn.cursor()

        c.execute("""
        INSERT INTO goals (user_id, name, target)
        VALUES (?,?,?)
        """, (get_user_id(),
              request.form['name'],
              target))

        conn.commit()
        conn.close()

        flash("Goal added 🎯")
        return redirect('/dashboard')

    return render_template('add_goal.html')


# ---------------- HISTORY (MAIN FIX) ----------------
@app.route('/history')
@login_required
def history():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT id, amount, category, date, note, 'expense' FROM expenses WHERE user_id=?
    UNION ALL
    SELECT id, amount, source, date, '', 'income' FROM income WHERE user_id=?
    ORDER BY date DESC
    """, (get_user_id(), get_user_id()))

    rows = c.fetchall()

    # 🔥 convert safely
    data = []
    for r in rows:
        row = list(r)
        row[1] = safe_float(row[1])  # amount
        data.append(row)

    total = sum(row[1] for row in data if row[5] == 'expense')
    income = sum(row[1] for row in data if row[5] == 'income')
    balance = income - total

    conn.close()

    return render_template('history.html',
                           data=data,
                           total=total,
                           income=income,
                           balance=balance)


# ---------------- EDIT ----------------
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM expenses WHERE id=? AND user_id=?", (id, user_id))
    data = c.fetchone()

    if not data:
        conn.close()
        return "Unauthorized ❌"

    if request.method == 'POST':
        amount = safe_float(request.form.get('amount'))
        category = request.form.get('category')
        custom = request.form.get('custom_category')

        if category == "Others" and custom:
            category = custom

        c.execute("""
        UPDATE expenses
        SET amount=?, category=?, date=?, note=?
        WHERE id=? AND user_id=?
        """, (amount, category,
              request.form.get('date'),
              request.form.get('note'),
              id, user_id))

        conn.commit()
        conn.close()

        flash("Updated ✏️")
        return redirect('/history')

    conn.close()
    return render_template('edit.html', data=data)


# ---------------- DELETE ----------------
@app.route('/delete/<int:id>')
@login_required
def delete(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (id, get_user_id()))

    conn.commit()
    conn.close()

    flash("Deleted 🗑")
    return redirect('/history')


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)