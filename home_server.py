import sqlite3
from flask import Flask, render_template, jsonify, request, url_for, flash, redirect
from werkzeug.exceptions import abort
from config import SECRET_KEY

# Database
def get_db_conn():
    conn = sqlite3.connect('database\\database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_post(post_id):
    conn = get_db_conn()
    post = conn.execute(
        'SELECT * FROM posts WHERE id = ?',
        (post_id,)
    ).fetchone()
    conn.close()
    if post is None:
        abort(404)
    return post

# Application
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/posts')
def posts():
    conn = get_db_conn()
    posts = conn.execute('SELECT * FROM posts').fetchall()
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
            conn = get_db_conn()
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
            conn = get_db_conn()
            conn.execute('UPDATE posts SET title = ?, content = ?'
                         ' WHERE id = ?',
                         (title, content, id))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))

    return render_template('edit.html', post=post)

@app.route('/<int:id>/delete', methods=('POST',))
def delete(id):
    post = get_post(id)
    conn = get_db_conn()
    conn.execute('DELETE FROM posts WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('"{}" was successfully deleted!'.format(post['title']))
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/api/status')
def api_status():
    return jsonify({
        "status": "success",
        "messaged": "Data recieved from home server"
    })

@app.route('/api/data')
def api_data():
    return jsonify({
        "key1": "data1",
        "key2": "data2"
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000) 
