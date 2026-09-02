from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret123'


# 🔗 DB CONNECT
def get_conn():
    return mysql.connector.connect(
        user='root',
        password='',
        host='localhost',
        database='skill_exchange_db'
    )


# 🏠 INDEX
@app.route('/')
def index():
    return render_template('index.html', year=datetime.now().year)


# 🧾 REGISTER
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM usertb WHERE Email=%s", (email,))
        if cursor.fetchone():
            flash("Email already exists!")
            return redirect('/register')

        cursor.execute("INSERT INTO usertb (Email, Password) VALUES (%s, %s)", (email, password))
        conn.commit()

        flash("Registered Successfully!")
        return redirect('/login')

    return render_template('register.html')


# 🔐 LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM usertb WHERE Email=%s AND Password=%s", (email, password))
        user = cursor.fetchone()

        if user is None:
            flash("Invalid Email or Password")
            return redirect('/login')

        # ✅ FIX: store user_id
        session['user_id'] = user[0]
        session['email'] = email

        return redirect('/home')

    return render_template('login.html')


@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_conn()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            u.id,
            u.FullName AS full_name,
            u.ProfileImage AS profile_image,
            u.Bio AS bio,
            GROUP_CONCAT(s.skill_name SEPARATOR ', ') as skills
        FROM usertb u
        LEFT JOIN user_skills us ON u.id = us.user_id
        LEFT JOIN skills s ON us.skill_id = s.id
        WHERE u.id != %s
        GROUP BY u.id
    """

    cursor.execute(query, (user_id,))
    users = cursor.fetchall()

    return render_template('home.html', users=users)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_conn()
    cursor = conn.cursor(dictionary=True)

    # ✅ ONLY ONE QUERY (with alias)
    cursor.execute("""
        SELECT 
            id,
            FullName AS full_name,
            Email AS email,
            Bio AS bio,
            ProfileImage AS profile_image
        FROM usertb 
        WHERE id=%s
    """, (user_id,))

    user = cursor.fetchone()

    if not user:
        flash("User not found")
        return redirect('/login')

    # ✅ skills query
    cursor.execute("""
        SELECT s.id, s.skill_name 
        FROM skills s
        JOIN user_skills us ON s.id = us.skill_id
        WHERE us.user_id=%s
    """, (user_id,))

    skills = cursor.fetchall()

    return render_template('profile.html', user=user, skills=skills)


# ➕ ADD SKILL
@app.route('/add_skill', methods=['POST'])
def add_skill():
    if 'user_id' not in session:
        return {"status": "error"}

    user_id = session['user_id']
    skill_name = request.form['skill_name']

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM skills WHERE skill_name=%s", (skill_name,))
    skill = cursor.fetchone()

    if skill:
        skill_id = skill[0]
    else:
        cursor.execute("INSERT INTO skills (skill_name) VALUES (%s)", (skill_name,))
        conn.commit()
        skill_id = cursor.lastrowid

    cursor.execute("SELECT * FROM user_skills WHERE user_id=%s AND skill_id=%s", (user_id, skill_id))
    if cursor.fetchone():
        return {"status": "exists"}

    cursor.execute("INSERT INTO user_skills (user_id, skill_id) VALUES (%s, %s)", (user_id, skill_id))
    conn.commit()

    return {"status": "success", "skill_id": skill_id, "skill_name": skill_name}


# ❌ DELETE SKILL
@app.route('/delete_skill', methods=['POST'])
def delete_skill():
    user_id = session['user_id']
    skill_id = request.form['skill_id']

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM user_skills WHERE user_id=%s AND skill_id=%s", (user_id, skill_id))
    conn.commit()

    return {"status": "success"}


import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/upload_profile_image', methods=['POST'])
def upload_profile_image():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    if 'profile_image' not in request.files:
        flash("No file selected")
        return redirect('/profile')

    file = request.files['profile_image']

    if file.filename == '':
        flash("No file selected")
        return redirect('/profile')

    filename = secure_filename(file.filename)

    # 🔥 UNIQUE NAME (avoid overwrite)
    filename = str(user_id) + "_" + filename

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # SAVE TO DB
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE usertb SET ProfileImage=%s WHERE id=%s
    """, (filename, user_id))

    conn.commit()

    flash("Profile image updated!")
    return redirect('/profile')


# 📝 UPDATE PROFILE
@app.route('/update_profile', methods=['POST'])
def update_profile():
    user_id = session['user_id']
    name = request.form['full_name']
    bio = request.form['bio']

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("UPDATE usertb SET FullName=%s, Bio=%s WHERE id=%s",
                   (name, bio, user_id))
    conn.commit()

    flash("Profile updated!")
    return redirect('/profile')


# 🔓 LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
@app.route('/chats')
def chats():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    other_user_id = request.args.get('user_id')

    conn = get_conn()
    cursor = conn.cursor(dictionary=True)

    active_chat_id = None

    # ✅ create/find chat
    if other_user_id:
        cursor.execute("""
            SELECT id FROM chats 
            WHERE (user_one_id=%s AND user_two_id=%s)
               OR (user_one_id=%s AND user_two_id=%s)
        """, (user_id, other_user_id, other_user_id, user_id))

        chat = cursor.fetchone()

        if chat:
            active_chat_id = chat['id']
        else:
            cursor.execute("""
                INSERT INTO chats (user_one_id, user_two_id)
                VALUES (%s, %s)
            """, (user_id, other_user_id))
            conn.commit()
            active_chat_id = cursor.lastrowid

    # ✅ get conversations
    cursor.execute("""
        SELECT 
            c.id as chat_id,
            u.id,
            u.FullName as full_name,
            u.ProfileImage as profile_image
        FROM chats c
        JOIN usertb u 
        ON u.id = IF(c.user_one_id = %s, c.user_two_id, c.user_one_id)
        WHERE c.user_one_id=%s OR c.user_two_id=%s
    """, (user_id, user_id, user_id))

    conversations = cursor.fetchall()

    return render_template('chats.html',
                           conversations=conversations,
                           active_chat_id=active_chat_id)

from flask import jsonify

@app.route('/get_messages', methods=['POST'])
def get_messages():
    chat_id = request.form['chat_id']

    conn = get_conn()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT sender_id, message
        FROM messages                    
        WHERE chat_id=%s
        ORDER BY id ASC
    """, (chat_id,))

    messages = cursor.fetchall()
    return jsonify(messages)

from flask import jsonify

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({"status": "error", "msg": "not logged in"})

    chat_id = request.form.get('chat_id')
    message = request.form.get('message')
    user_id = session['user_id']

    if not chat_id or not message:
        return jsonify({"status": "error", "msg": "missing data"})

    if message.strip() == "":
        return jsonify({"status": "error", "msg": "empty message"})

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO messages (chat_id, sender_id, message)
        VALUES (%s, %s, %s)
    """, (chat_id, user_id, message))

    conn.commit()

    return jsonify({"status": "success"})


if __name__ == '__main__':
    app.run(debug=True)