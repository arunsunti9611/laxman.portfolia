import os
import json
import sqlite3
import logging
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

import subprocess
import cv2
import numpy as np
import base64

# Initialize AI Face Detector
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
BIOMETRIC_DIR = 'security/biometrics'
if not os.path.exists(BIOMETRIC_DIR):
    os.makedirs(BIOMETRIC_DIR)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'laxman_secure_mirror_key_2024')
app.config['UPLOAD_FOLDER'] = 'static/assets/img'
app.config['DB_PATH'] = 'site_data.db'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=60) # 1 min limit
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=40) # 40 sec limit

# Self-Ping to keep Render awake
def keep_alive_pulse():
    import time
    import urllib.request
    import os
    port = os.environ.get("PORT", "5000")
    while True:
        try:
            # Pings its own login page to stay active
            urllib.request.urlopen(f"http://localhost:{port}/admin/keep_alive")
        except:
            pass
        time.sleep(600) # Every 10 mins

import threading
threading.Thread(target=keep_alive_pulse, daemon=True).start()

# Advanced Hardware & Cloud Security
ALLOWED_UUID = "0345DA65-3283-417D-B72D-E88CC68027A8"

def get_current_hwid():
    try:
        # Windows check
        if os.name == 'nt':
            cmd = 'powershell -Command "(Get-CimInstance Win32_ComputerSystemProduct).UUID"'
            return subprocess.check_output(cmd, shell=True).decode().strip()
        # Linux / Render check
        else:
            for path in ['/sys/class/dmi/id/product_uuid', '/etc/machine-id']:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        return f.read().strip()
        return "CLOUD_SERVER"
    except:
        return "UNKNOWN"

def get_dynamic_password():
    # Formula: laxman + DDMMHHMM
    return "laxman" + datetime.now().strftime("%d%m%H%M")

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

def get_db_connection():
    conn = sqlite3.connect(app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    return conn

def calculate_tenure(start_str, end_str=None, is_present=False, existing_tenure=None):
    if not start_str and existing_tenure:
        return existing_tenure
    
    try:
        formats = ["%b %Y", "%B %Y", "%Y-%m-%d", "%m/%Y", "%Y"]
        start_date = None
        for fmt in formats:
            try:
                start_date = datetime.strptime(start_str.strip(), fmt)
                break
            except: continue
        
        if not start_date: 
            return start_str if start_str else (existing_tenure if existing_tenure else "")

        if is_present:
            end_date = datetime.now()
        else:
            end_date = None
            if end_str:
                for fmt in formats:
                    try:
                        end_date = datetime.strptime(end_str.strip(), fmt)
                        break
                    except: continue
            if not end_date: 
                return f"{start_str} - {end_str}" if end_str else start_str

        diff = relativedelta(end_date, start_date)
        years = diff.years
        months = diff.months
        
        parts = []
        if years > 0: parts.append(f"{years} yr{'s' if years > 1 else ''}")
        if months > 0: parts.append(f"{months} mo{'s' if months > 1 else ''}")
        
        duration = f"({', '.join(parts)})" if parts else ""
        display_end = "Present" if is_present else (end_str if end_str else "")
        
        return f"{start_str} - {display_end} {duration}".strip()
    except Exception as e:
        return existing_tenure if existing_tenure else start_str

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS site_data (key TEXT PRIMARY KEY, value TEXT)')
    
    cursor.execute('SELECT COUNT(*) FROM site_data WHERE key = "last_updated"')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO site_data (key, value) VALUES (?, ?)', ('last_updated', str(time.time())))
    
    cursor.execute('SELECT value FROM site_data WHERE key = "experience"')
    row = cursor.fetchone()
    if row:
        exps = json.loads(row[0])
        modified = False
        for exp in exps:
            if not exp.get('start_date') and exp.get('tenure'):
                parts = exp['tenure'].split('-')
                if len(parts) >= 1:
                    exp['start_date'] = parts[0].strip()
                    if 'Present' in exp['tenure']:
                        exp['is_present'] = True
                        exp['end_date'] = ""
                    elif len(parts) >= 2:
                        end_part = parts[1].split('(')[0].strip()
                        exp['end_date'] = end_part
                    modified = True
        if modified:
            cursor.execute('INSERT OR REPLACE INTO site_data (key, value) VALUES (?, ?)', ('experience', json.dumps(exps)))
            conn.commit()
    conn.close()

def get_site_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM site_data')
    rows = cursor.fetchall()
    conn.close()
    data = {row['key']: (json.loads(row['value']) if row['key'] != 'last_updated' else row['value']) for row in rows}
    
    if 'profile' not in data: data['profile'] = {}
    
    if 'experience' in data:
        data['experience'].sort(key=lambda x: (x.get('is_present', False), x.get('id', 0)), reverse=True)
        for exp in data['experience']:
            exp['tenure'] = calculate_tenure(exp.get('start_date', ''), exp.get('end_date', ''), exp.get('is_present', False), exp.get('tenure'))
    
    for collection in ['education', 'experience', 'skills', 'projects']:
        if collection in data:
            for item in data[collection]:
                if 'is_visible' not in item: item['is_visible'] = True
    
    data['skill_categories'] = sorted(list(set(s.get('category', 'Technical') for s in data.get('skills', []))))
    data['v'] = int(time.time())
    return data

def save_site_data(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO site_data (key, value) VALUES (?, ?)', (key, json.dumps(value) if key != 'last_updated' else str(value)))
    if key != 'last_updated':
        cursor.execute('INSERT OR REPLACE INTO site_data (key, value) VALUES (?, ?)', ('last_updated', str(time.time())))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html', **get_site_data())

@app.route('/api/last_updated')
def last_updated():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM site_data WHERE key = "last_updated"')
    row = cursor.fetchone()
    conn.close()
    return jsonify({"last_updated": row[0] if row else "0"})

@app.route('/skills', endpoint='skills')
def skills_page():
    return render_template('skills.html', **get_site_data())

@app.route('/projects', endpoint='projects')
def projects_page():
    return render_template('projects.html', **get_site_data())

@app.route('/admin/dashboard')
@login_required
def dashboard():
    return render_template('admin/dashboard.html', **get_site_data())

@app.route('/admin/update_profile', methods=['POST'])
@login_required
def update_profile():
    data_store = get_site_data()
    profile = data_store['profile']
    form_data = request.form.to_dict()
    
    if 'field_key' in form_data:
        key = form_data['field_key']
        value = form_data.get(key)
        if key.startswith('social.'): profile['social'][key.split('.')[1]] = value
        else: profile[key] = value
    else:
        for k, v in form_data.items():
            if k.startswith('social.'): profile['social'][k.split('.')[1]] = True if v == 'True' else (False if v == 'False' else v)
            elif k == 'titles_raw': profile['titles'] = [t.strip() for t in v.split(',') if t.strip()]
            elif k == 'strengths_raw': profile['strengths'] = [s.strip() for s in v.split(',') if s.strip()]
            elif k not in ['field_key']: profile[k] = v
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '': file.save(os.path.join(app.config['UPLOAD_FOLDER'], "profile-img.jpg"))
            
    save_site_data('profile', profile)
    return redirect(url_for('dashboard'))

@app.route('/admin/update_item/<collection>/<int:item_id>', methods=['POST'])
@login_required
def update_item(collection, item_id):
    data_store = get_site_data()
    items = data_store.get(collection, [])
    form_data = request.form.to_dict()
    if 'details' in form_data: form_data['details'] = [d.strip() for d in form_data['details'].split('\n') if d.strip()]
    if 'percentage' in form_data: form_data['percentage'] = int(form_data['percentage'])
    if collection == 'experience':
        form_data['is_present'] = True if 'is_present' in request.form or request.form.get('is_present') == 'True' else False
    if 'is_visible' in request.form: form_data['is_visible'] = True if request.form.get('is_visible') == 'True' else False
    for i, item in enumerate(items):
        if item.get('id') == item_id:
            items[i].update(form_data)
            break
    save_site_data(collection, items)
    return redirect(url_for('dashboard'))

@app.route('/admin/add_experience', methods=['POST'])
@login_required
def add_experience():
    data_store = get_site_data()
    exp_list = data_store.get('experience', [])
    new_id = max([e.get('id', 0) for e in exp_list] + [0]) + 1
    is_present = True if request.form.get('is_present') else False
    exp_list.append({"id": new_id, "role": request.form.get('role'), "company": request.form.get('company'), "start_date": request.form.get('start_date'), "end_date": request.form.get('end_date', ''), "is_present": is_present, "is_visible": True, "location": request.form.get('location'), "details": [d.strip() for d in request.form.get('details', '').split('\n') if d.strip()]})
    save_site_data('experience', exp_list)
    return redirect(url_for('dashboard'))

@app.route('/admin/add_skill', methods=['POST'])
@login_required
def add_skill():
    data_store = get_site_data()
    skills = data_store.get('skills', [])
    category = request.form.get('category_new') if request.form.get('category') == 'NEW' else request.form.get('category')
    new_id = max([s.get('id', 0) for s in skills] + [0]) + 1
    skills.append({"id": new_id, "name": request.form.get('name'), "category": category, "percentage": int(request.form.get('percentage', 0)), "is_visible": True})
    save_site_data('skills', skills)
    return redirect(url_for('dashboard'))

@app.route('/admin/add_education', methods=['POST'])
@login_required
def add_education():
    data_store = get_site_data()
    edu_list = data_store.get('education', [])
    new_id = max([e.get('id', 0) for e in edu_list] + [0]) + 1
    edu_list.append({"id": new_id, "degree": request.form.get('degree'), "institution": request.form.get('institution'), "tenure": request.form.get('tenure'), "percentage": request.form.get('percentage'), "is_visible": True})
    save_site_data('education', edu_list)
    return redirect(url_for('dashboard'))

@app.route('/admin/add_project', methods=['POST'])
@login_required
def add_project():
    data_store = get_site_data()
    proj_list = data_store.get('projects', [])
    new_id = max([p.get('id', 0) for p in proj_list] + [0]) + 1
    proj_list.append({"id": new_id, "title": request.form.get('title'), "description": request.form.get('description'), "is_visible": True})
    save_site_data('projects', proj_list)
    return redirect(url_for('dashboard'))

@app.route('/admin/delete_skill/<int:id>')
@login_required
def delete_skill(id):
    data_store = get_site_data()
    save_site_data('skills', [s for s in data_store.get('skills', []) if s.get('id') != id])
    return redirect(url_for('dashboard'))

@app.route('/admin/delete_experience/<int:id>')
@login_required
def delete_experience(id):
    data_store = get_site_data()
    save_site_data('experience', [e for e in data_store.get('experience', []) if e.get('id') != id])
    return redirect(url_for('dashboard'))

@app.route('/admin/delete_education/<int:id>')
@login_required
def delete_education(id):
    data_store = get_site_data()
    save_site_data('education', [e for e in data_store.get('education', []) if e.get('id') != id])
    return redirect(url_for('dashboard'))

@app.route('/admin/delete_project/<int:id>')
@login_required
def delete_project(id):
    data_store = get_site_data()
    save_site_data('projects', [p for p in data_store.get('projects', []) if p.get('id') != id])
    return redirect(url_for('dashboard'))

def get_dynamic_password():
    # Full Dynamic Formula: DDMMYYYY + HHMM
    return datetime.now().strftime("%d%m%Y%H%M")

@app.route('/admin/verify_biometrics', methods=['POST'])
def verify_biometrics():
    data = request.get_json()
    img_data = data.get('image').split(',')[1]
    nparr = np.frombuffer(base64.b64decode(img_data), np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Real Face Detection
    faces = face_cascade.detectMultiScale(gray, 1.05, 5, minSize=(100, 100))
    if len(faces) == 0:
        return jsonify({'success': False, 'message': 'NO FACE DETECTED: PLEASE ADJUST LIGHTING'})
    
    x, y, w, h = faces[0]
    face_roi = cv2.resize(gray[y:y+h, x:x+w], (128, 128))
    
    # Advanced Normalization (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    face_roi = clahe.apply(face_roi)
    
    # Get the unique Hardware ID (Device DNA)
    device_id = request.cookies.get('device_dna')
    if not device_id:
        return jsonify({'success': False, 'message': 'DEVICE NOT AUTHORIZED'})

    # 2. Get/Set Master from Database (Per Device)
    conn = sqlite3.connect(app.config['DB_PATH'])
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS biometrics (device_id TEXT PRIMARY KEY, master_blob BLOB)")
    
    cursor.execute("SELECT master_blob FROM biometrics WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    
    if not row:
        # ENROLLMENT: Save to DB for THIS specific device
        _, buffer = cv2.imencode('.png', face_roi)
        master_blob = buffer.tobytes()
        cursor.execute("INSERT INTO biometrics (device_id, master_blob) VALUES (?, ?)", (device_id, master_blob))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'enrolled': True, 'message': f'MASTER ENROLLED FOR THIS DEVICE'})
    
    # 3. VERIFICATION: ORB Feature Matching (More robust than Histograms)
    master_blob = row[0]
    nparr_master = np.frombuffer(master_blob, np.uint8)
    master_img = cv2.imdecode(nparr_master, cv2.IMREAD_GRAYSCALE)
    master_img = clahe.apply(master_img)
    
    # Initialize ORB detector
    orb = cv2.ORB_create(nfeatures=500)
    kp1, des1 = orb.detectAndCompute(master_img, None)
    kp2, des2 = orb.detectAndCompute(face_roi, None)
    
    if des1 is None or des2 is None:
        return jsonify({'success': False, 'message': 'FEATURE EXTRACTION FAILED: TRY BETTER LIGHTING'})

    # Brute-Force Matcher
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    
    # Sort matches by distance
    matches = sorted(matches, key=lambda x: x.distance)
    
    # Calculate score based on good matches (distance < 50)
    good_matches = [m for m in matches if m.distance < 45]
    match_ratio = len(good_matches) / max(len(kp1), 1)
    
    conn.close()
    
    if match_ratio > 0.15: # 15% feature match threshold for ORB
        from flask import session
        session['biometrics_passed'] = True
        return jsonify({'success': True, 'message': 'IDENTITY MATCHED'})
    else:
        from flask import session
        session['biometrics_failed_on_device'] = device_id
        return jsonify({'success': False, 'message': 'IDENTITY MISMATCH: RE-SCAN'})

@app.route('/admin/keep_alive')
def keep_alive():
    return jsonify({'status': 'active'})

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    # Authorized Web-DNA IDs (Whitelist)
    AUTHORIZED_DEVICES = ['LAXMAN-MASTER-KEY-2024', 'DEV-392DCB80']
    
    # 1. HARDWARE PERIMETER CHECK (LAYER 1)
    device_id = request.cookies.get('device_dna')
    
    # Developer Laptop Override (Localhost only)
    if not device_id and request.remote_addr in ['127.0.0.1', '::1']:
        device_id = 'LAXMAN-MASTER-KEY-2024'

    if not device_id or device_id not in AUTHORIZED_DEVICES:
        temp_id = device_id if device_id else "DEV-" + os.urandom(4).hex().upper()
        resp = make_response(f"""
            <body style='background:#0a0a0a; color:#ff4d4d; font-family:sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; text-align:center;'>
                <div>
                    <h1 style='font-size:3rem;'>ACCESS DENIED</h1>
                    <p style='color:#888;'>Unauthorized Hardware Detected.<br>Device DNA: <b>{temp_id}</b></p>
                </div>
            </body>
        """, 403)
        if not device_id: resp.set_cookie('device_dna', temp_id, max_age=31536000) 
        return resp

    # 2. LOGIN LOGIC (LAYER 2 & 3)
    # Sync with IST (Asia/Kolkata) to match user's phone time
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    possible_passwords = [
        (ist_now - timedelta(minutes=1)).strftime("%d%m%Y%H%M"),
        ist_now.strftime("%d%m%Y%H%M"),
        (ist_now + timedelta(minutes=1)).strftime("%d%m%Y%H%M")
    ]

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'laxman' and password in possible_passwords:
            # Check if biometrics were bypassed after failure
            if session.get('biometrics_failed_on_device') == device_id:
                # Force re-enrollment on next biometric scan
                conn = sqlite3.connect(app.config['DB_PATH'])
                cursor = conn.cursor()
                cursor.execute("DELETE FROM biometrics WHERE device_id = ?", (device_id,))
                conn.commit()
                conn.close()
                flash('Biometrics Reset: Please re-enroll on next login.')

            user = User("1")
            login_user(user, remember=False)
            session.pop('biometrics_failed_on_device', None)
            return redirect(url_for('dashboard'))
        
        flash('Invalid Credentials or Biometric Mismatch.')
    
    return render_template('admin/login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']): os.makedirs(app.config['UPLOAD_FOLDER'])
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
