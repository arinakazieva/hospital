# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///hospital.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки для загрузки аватарок
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Создаем папку для загрузок, если ее нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), default='patient')
    avatar = db.Column(db.String(200), default='default_avatar.png') # Новое поле

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    specialty = db.Column(db.String(120))

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(255))
    user = db.relationship('User', backref=db.backref('appointments', lazy=True))
    doctor = db.relationship('Doctor', backref=db.backref('appointments', lazy=True))

# Создаем базу данных
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('index.html', logged_in='user_id' in session)

# --- НОВЫЙ МАРШРУТ: ПРОФИЛЬ ---
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    appointments = Appointment.query.filter_by(user_id=user.id).all()

    if request.method == 'POST':
        # Обработка загрузки аватарки
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # Уникальное имя файла: user_ID_имя.jpg
                unique_filename = f"user_{user.id}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                
                # Сохраняем в БД
                user.avatar = unique_filename
                db.session.commit()
                flash('Аватарка успешно обновлена!', 'success')
                return redirect(url_for('profile'))

    return render_template('profile.html', user=user, appointments=appointments)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash("Username already exists", "error")
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return render_template('register.html')

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("Регистрация успешна! Пожалуйста, войдите.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('profile')) # После входа кидаем сразу в профиль
        else:
            flash("Invalid username or password", "error")
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/appointment', methods=['GET', 'POST'])
def appointment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctors = Doctor.query.all()
    if request.method == 'POST':
        doctor_id = int(request.form['doctor'])
        appointment_date_str = request.form['appointment_date']
        reason = request.form['reason']

        try:
            appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash("Invalid date format", "error")
            return render_template('appointment.html', doctors=doctors)

        new_appointment = Appointment(user_id=session['user_id'], doctor_id=doctor_id, appointment_date=appointment_date, reason=reason)
        db.session.add(new_appointment)
        db.session.commit()
        flash("Вы успешно записались на прием!", "success")
        return redirect(url_for('profile'))

    return render_template('appointment.html', doctors=doctors)

@app.route('/admin/add_doctor', methods=['GET', 'POST'])
def add_doctor():
    if 'user_id' not in session or session['role'] != 'admin':
        return "Unauthorized", 403

    if request.method == 'POST':
        name = request.form['name']
        specialty = request.form['specialty']
        new_doctor = Doctor(name=name, specialty=specialty)
        db.session.add(new_doctor)
        db.session.commit()
        flash("Doctor added successfully!", "success")
        return redirect(url_for('admin_panel'))
    return render_template('add_doctor.html')

@app.route('/admin')
def admin_panel():
  if 'user_id' in session and session['role'] == 'admin':
    return render_template('admin_panel.html')
  return "Unauthorized", 403

if __name__ == '__main__':
    with app.app_context():
        # Создаем админа, если нет
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@example.com', role='admin')
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()

        # Создаем тестового врача
        if not Doctor.query.filter_by(name='Др. Тестов').first():
            db.session.add(Doctor(name='Др. Тестов', specialty='Терапевт'))
            db.session.commit()

    app.run(debug=True)