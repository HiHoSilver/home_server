import time
from threading import Thread, Event
import sqlite3
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import platform
import atexit
from flask import Flask, render_template, jsonify, request, url_for, flash, redirect
from werkzeug.exceptions import abort
import pandas as pd
from plotly.utils import PlotlyJSONEncoder
import plotly.express as px
import requests
from config import SECRET_KEY
from arduino import send_msg_to_arduino

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

# For notification timer
NOTIFICATION_TIMER_FLAG = False
led_state = False
stop_event = Event()

# For server status endpoint
start_time = time.time()
request_count = 0
SERVER_VERSION = "0.0.1"

# -----------Databases-----------
def get_posts_db_conn():
    conn = sqlite3.connect('database\\posts_database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_post(post_id):
    conn = get_posts_db_conn()
    post = conn.execute(
        'SELECT * FROM posts WHERE id = ?',
        (post_id,)
    ).fetchone()
    conn.close()
    if post is None:
        abort(404)
    return post

def get_thermo_db_conn():
    conn = sqlite3.connect('database\\thermo_database.db')
    conn.row_factory = sqlite3.Row
    return conn

# -----------Timer for ESP32 LEDs-----------
def notification_timer_worker():
    # Capture the flag ONCE at startup
    if not NOTIFICATION_TIMER_FLAG:
        print("LED notification timer disabled at startup.")
        # Still keep the thread alive so shutdown works cleanly
        while not stop_event.is_set():
            time.sleep(1)
        return

    print("LED notification timer enabled at startup.")

    while not stop_event.is_set():
        if led_state:
            print("Timer started...")

            for _ in range(6):
                if stop_event.is_set() or not led_state:
                    print("Timer ended...")
                    break
                time.sleep(1)

            if led_state and not stop_event.is_set():
                print("Timer up. Restarting...")

        else:
            time.sleep(1)

# -----------Web App-----------
# Request counter
@app.before_request
def count_requests():
    global request_count
    request_count += 1

# Index page
@app.route('/')
def index():
    return render_template('index.html')

# Posts page and managing Posts
@app.route('/posts')
def posts():
    conn = get_posts_db_conn()
    posts = conn.execute('SELECT * FROM posts ORDER BY created DESC').fetchall()
    conn.close
    return render_template('posts.html', posts=posts)

@app.route('/<int:post_id>')
def view_post(post_id):
    post = get_post(post_id)
    return render_template('view_post.html', post=post)

@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            conn = get_posts_db_conn()
            conn.execute(
                'INSERT INTO posts (title, content) VALUES (?, ?)',
                (title, content)
            )
            conn.commit()
            conn.close()
            return redirect(url_for('index'))

    return render_template('create.html')

@app.route('/<int:id>/edit', methods=('GET', 'POST'))
def edit(id):
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            conn = get_posts_db_conn()
            conn.execute('UPDATE posts SET title = ?, content = ?'
                         ' WHERE id = ?',
                         (title, content, id)
            )
            conn.commit()
            conn.close()
            return redirect(url_for('index'))

    return render_template('edit.html', post=post)

@app.route('/<int:id>/delete', methods=('POST',))
def delete(id):
    post = get_post(id)
    conn = get_posts_db_conn()
    conn.execute('DELETE FROM posts WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('"{}" was successfully deleted!'.format(post['title']))
    return redirect(url_for('index'))

@app.route('/graph')
def graph():
    with get_thermo_db_conn() as conn:
        df = pd.read_sql_query(
            'SELECT * FROM thermo ORDER BY id DESC LIMIT 24',
            conn
        )

    df = df.iloc[::-1]
    df['created'] = pd.to_datetime(df['created'])

    df['temperature_f'] = (df['temperature'] * 1.8) + 32
    df['created'] = (
        pd.to_datetime(df['created'], utc=True)
        .dt.tz_convert(ZoneInfo("America/New_York"))
    )

    fig = px.line(
        df,
        x='created',
        y=['temperature_f', 'humidity'],
        title='Temperature & Humidity (Last 24 Readings)',
        labels={'value': 'Reading', 'variable': 'Measurement', 'created': 'Time (Eastern)'}
    )

    # Rename legend entries
    fig.data[0].name = "Temperature (°F)"
    fig.data[1].name = "Humidity (%)"

    # Style the legend
    fig.update_layout(
        legend=dict(
            title="Sensors",
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="right",
            x=1
        )
    )

    graphJSON = json.dumps(fig, cls=PlotlyJSONEncoder)

    return render_template('graph.html', graphJSON=graphJSON)

# About page
@app.route('/about')
def about():
    return render_template('about.html')

# Data endpoint
@app.route('/api/data')
def api_data():
    conn = get_thermo_db_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Total row count
    cur.execute("SELECT COUNT(*) FROM thermo")
    row_count = cur.fetchone()[0]

    # Latest reading
    cur.execute("""
        SELECT device_id, created, temperature, humidity
        FROM thermo
        ORDER BY created DESC
        LIMIT 1
    """)
    latest = cur.fetchone()

    conn.close()

    # If no data exists yet
    if latest is None:
        return jsonify({
            "row_count": row_count,
            "latest": None
        })

    return jsonify({
        "row_count": row_count,
        "latest": {
            "device_id": latest["device_id"],
            "created": latest["created"],
            "temperature": latest["temperature"],
            "humidity": latest["humidity"]
        }
    })

# Thermo endpoint
@app.route('/api/thermo', methods=['POST'])
def api_thermo():
    data = request.get_json()

    required = ("device_id", "temperature", "humidity")
    if not data or not all(k in data for k in required):
        return jsonify({"error": "Invalid payload"}), 400

    # Type validation
    try:
        temperature = float(data["temperature"])
        humidity = float(data["humidity"])
    except (ValueError, TypeError):
        return jsonify({"error": "Temperature and humidity must be numbers"}), 400

    with get_thermo_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO thermo (device_id, temperature, humidity) VALUES (?, ?, ?)",
            (data["device_id"], temperature, humidity)
        )
        row_id = cur.lastrowid

    return jsonify({"status": "ok", "id": row_id}), 200

# Server status endpoint
def format_uptime(seconds):
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return f"{days}d {hours}h {minutes}m {seconds}s"

# ESP32 LED endpoint
esp_ips = ['192.168.1.30', '192.168.1.31']
led_state = False
last_seen = {}      # TODO: Expose as endpoint?

@app.route('/api/esp32_led', methods=['GET', 'POST'])
def esp32_led():
    global led_state, last_seen

    if request.method == 'GET':
        sender_ip = request.remote_addr
        last_seen[sender_ip] = datetime.now(ZoneInfo("America/New_York"))

        return jsonify({
            'state': led_state,
            'last_seen': last_seen[sender_ip].isoformat()
        }), 200

    if request.method == 'POST':
        sender_ip = request.remote_addr
        last_seen[sender_ip] = datetime.now(ZoneInfo("America/New_York"))

        data = request.get_json(silent=True) or {}
        state = data.get('state')

        if state == 'on':
            led_state = True
        elif state == 'off':
            led_state = False
            stop_event.set()      # wakes the thread immediately
            stop_event.clear()    # reset for next cycle
        else:
            return jsonify({'error': 'invalid state'}), 400

        # Broadcast to all ESP32s
        for target_ip in esp_ips:
            try:
                response = requests.post(
                    f"http://{target_ip}/led",
                    json={"state": state},
                    timeout=2
                )
                print(f"Broadcast to {target_ip}: {response.status_code}")
            except Exception as e:
                print(f"Error sending to {target_ip}: {e}")

        return jsonify({'success': True, 'state': led_state}), 200

@app.route('/api/server_status')
def server_status():
    uptime_seconds = int(time.time() - start_time)

    return jsonify({
        "uptime_seconds": uptime_seconds,
        "uptime_time": format_uptime(uptime_seconds),
        "requests_handled": request_count,
        "server_version": SERVER_VERSION,
        "python_version": platform.python_version()
    })

# Shutdown tasks
def on_shutdown():
    print("Server is shutting down...")

    # Signal the worker thread to stop immediately
    stop_event.set()

    # Wait for the worker thread to exit cleanly
    worker_thread.join()

atexit.register(on_shutdown)

if __name__ == "__main__":
    # send_msg_to_arduino("  Home server active...")
    worker_thread = Thread(target=notification_timer_worker, daemon=True)
    worker_thread.start()
    app.run(host='0.0.0.0', port=5000)
 