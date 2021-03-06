"""
If you encounter no module named flask_sqlalchemy after running install_packages.sh 
just run this command "source venv/bin/activate"
"""

from flask import render_template, flash, redirect, url_for, request, send_from_directory, Response
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, PostForm, ResetPasswordRequestForm, ResetPasswordForm, EditThresholdForm
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User, Post, SensorThreshold, CSV
from werkzeug.urls import url_parse
from datetime import datetime
from app.email import send_password_reset_email
from collections import OrderedDict
from importlib import import_module
import os
import time
import atexit
import random
import csv
import sys
#import Adafruit_DHT

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

if os.environ.get('CAMERA'):
    Camera = import_module('camera_' + os.environ['CAMERA']).Camera
else:
    from camera import Camera

from camera_pi import Camera

def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def get_temp_humid(pin):
    if pin == '4':
        temperature, humidity = 26, 99
    else:
        temperature, humidity = 0, 0
    #humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, '4')
    if humidity is not None and temperature is not None:
        temperature = "{0:0.1f}".format(temperature)
        humidity = "{0:0.1f}".format(humidity)
        #print('Temp={0:0.1f}*  Humidity={1:0.1f}%'.format(temperature, humidity))
        return temperature, humidity
    else:
        return 0, 0
    

def write_temp_csv():
    temperature, humidity = get_temp_humid('4')
    timeC = time.strftime("%I")+':' +time.strftime("%M")+':'+time.strftime("%S")
    data = [temperature, humidity, timeC]

    file_path = os.path.join(app.config['DATA_DIR'], 'temp_1.csv')
    with open(file_path, 'a') as output:
        writer_csv = csv.writer(output, delimiter=",", lineterminator = '\n')
        writer_csv.writerow(data)


def get_csv(filename):
    if filename is None:
        filename = 'temp_1.csv'
    file_path = os.path.join(app.config['DATA_DIR'], filename)
    with open(file_path, 'r') as output:
        return list(csv.reader(output, delimiter=','))

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
	logout_user()
	return redirect(url_for('index'))

@app.route('/camera')
def camera_page():
    return render_template('camera.html', title='Live Feed')    

@app.route('/live_feed')
def video_feed():
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/users')
@login_required
def users():
    if current_user.user_type != 'Admin':
        return redirect(url_for('index'))

    users = User.query.all()
    return render_template('users.html', title='Users', users=users, current_user=current_user)

@app.route('/delete/<int:id>', methods=['POST'])
def remove(id):
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash('User successfully deleted!')
    return redirect(url_for('users'))

@app.route('/camera')
def camera():
    return render_template('camera.html', title='Camera')

@app.route('/sensor')
@login_required
def sensor():
    temp_list = get_csv('20181306_Temperature_Humidity_Sensor1.csv')
    s1_temp, s1_humid = get_temp_humid('4')
    s2_temp, s2_humid = get_temp_humid('1')
    s3_temp, s3_humid = get_temp_humid('2')
    time = []
    temp_values = []
    humid_values = []
    for result in temp_list[-20:]:
        temp_values.append(result[0])
        humid_values.append(result[1])
        time.append(result[2])

    return render_template('sensor.html', title='Sensor', s1_cur_temp=s1_temp, s1_cur_humid=s1_humid, 
        s2_cur_temp=s2_temp, s2_cur_humid=s2_humid, 
        s3_cur_temp=s3_temp, s3_cur_humid=s3_humid, 
        temp_values=temp_values, humid_values=humid_values, labels=time)

@app.route('/csv')
@login_required
def csv_page():
    csv_data = CSV.query.all()
    return render_template('csv.html', title='Data Logs', csv_data=csv_data)

@app.route('/download/<path:filename>', methods=['GET', 'POST'])
def download(filename):    
    return send_from_directory(directory='data', filename=filename)

@app.route('/csv/<path:filename>', methods=['GET', 'POST'])
def populate_chart(filename):
    csv_data = CSV.query.all()
    temp_list = get_csv(filename)
    time = []
    temp_values = []
    humid_values = []
    for result in temp_list[-20:]:
        temp_values.append(result[0])
        humid_values.append(result[1])
        time.append(result[2])
    return render_template('csv.html', title='Data Logs', csv_data=csv_data, filename=filename,
        temp_values=temp_values, humid_values=humid_values, labels=time)

@app.route('/register/<string:user_type>', methods=['GET', 'POST'])
def register(user_type):
    if current_user.is_authenticated and user_type == 'Guest':
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, name=form.name.data, user_type=user_type)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        if user_type == 'Admin':
            flash(form.name.data + " is now registered!")
            return redirect(url_for('users'))
        flash('Congratulations, you are now registered!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form, user_type=user_type)

@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    sensor_threshold = SensorThreshold.query.get(1)
    page = request.args.get('page', 1, type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('user', username=user.username, page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('user', username=user.username, page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('user.html', user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url, sensor_threshold=sensor_threshold, title='User Page')

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.name = form.name.data
        current_user.email = form.email.data
        current_user.user_type = form.user_type.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.name.data = current_user.name
        form.email.data = current_user.email
        form.user_type.data = current_user.user_type
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile', form=form)

@app.route('/edit_threshold', methods=['GET', 'POST'])
@login_required
def edit_threshold():
    form = EditThresholdForm()
    sensor_threshold = SensorThreshold.query.get(1)
    if form.validate_on_submit():
        sensor_threshold.temp = form.temp.data
        sensor_threshold.water = form.water.data
        sensor_threshold.smoke = form.smoke.data
        sensor_threshold.humid = form.smoke.humid
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_threshold'))
    elif request.method == 'GET':
        form.temp.data = sensor_threshold.temp
        form.water.data = sensor_threshold.water
        form.smoke.data = sensor_threshold.smoke
        form.humid.data = sensor_threshold.humid
    return render_template('edit_threshold.html', title='Edit Threshold', form=form)

@app.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username))
        return redirect(url_for('index'))
    if user == current_user:
        flash('You cannot follow yourself!')
        return redirect(url_for('user', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('You are following {}!'.format(username))
    return redirect(url_for('user', username=username))

@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username))
        return redirect(url_for('index'))
    if user == current_user:
        flash('You cannot unfollow yourself!')
        return redirect(url_for('user', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('You are not following {}.'.format(username))
    return redirect(url_for('user', username=username))

@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template("index.html", title='Explore', posts=posts.items,
                          next_url=next_url, prev_url=prev_url)

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


#scheduler = BackgroundScheduler()
#scheduler.start()
#scheduler.add_job(
#    func=write_temp_csv,
#    trigger=IntervalTrigger(seconds=5),
#    id='temp_1_job',
#    name='Reading temp on pin 4.',
#    replace_existing=True)
# Shut down the scheduler when exiting the app
#atexit.register(lambda: scheduler.shutdown())