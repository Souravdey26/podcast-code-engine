from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import os
import pandas as pd
import mysql.connector
import logging
from datetime import datetime
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')

UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

podcast_db_config = {
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASS', '@Gultu2025'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'podcast_db'),
    'port': int(os.getenv('DB_PORT', 3306))
}

logging.basicConfig(level=logging.INFO)

# Skip loading CSV file in production
logging.info("Skipping CSV load — using database only")
podcasts_df = pd.DataFrame()

def test_mysql_connection():
    try:
        with mysql.connector.connect(**podcast_db_config):
            logging.info("MySQL connection OK")
    except Exception as e:
        logging.error(f"MySQL connection error: {e}")

test_mysql_connection()

def load_podcast_dataset(csv_path):
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        'Title': 'title',
        'Views': 'views',
        'Upload Date': 'upload_date',
        'Description': 'description',
        'URL': 'url',
        'Podcaster': 'podcaster'
    })
    df['upload_date'] = pd.to_datetime(df['upload_date'], errors='coerce')
    df['upload_date'] = df['upload_date'].dt.strftime('%Y-%m-%d')
    df['description'] = df['description'].astype(str).str.replace('#', '')
    df.fillna('', inplace=True)
    df.insert(0, 'id', range(len(df)))
    return df

def populate_podcasts_table(df):
    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor()
    insert_sql = (
        "INSERT INTO podcasts (title, views, upload_date, description, url, podcaster) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    data = df[['title','views','upload_date','description','url','podcaster']].values.tolist()
    try:
        cursor.executemany(insert_sql, data)
        conn.commit()
        logging.info(f"Inserted {len(data)} podcast records")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error inserting podcasts: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

VALID_USERS = {
    'Sourav': 'sourav2025',
    'Ayan': 'ayan2025',
    'Ribhu': 'ribhu2025'
}

@app.route('/', methods=['GET', 'POST'])
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)
    per_page = 100
    offset = (page - 1) * per_page

    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM podcasts ORDER BY id ASC LIMIT %s OFFSET %s", (per_page, offset))

    rows = cursor.fetchall()

    cursor.execute("SELECT article_id, coder, importance, notes, status FROM codes")
    codes = {r['article_id']: r for r in cursor.fetchall()}
    cursor.close()
    conn.close()

    articles = []
    for row in rows:
        art = row
        code = codes.get(row['id'], {})
        art['coded'] = bool(code)
        art['coder'] = code.get('coder', '')
        art['importance'] = code.get('importance', '')
        art['notes'] = code.get('notes', '')
        art['status'] = code.get('status') or 'pending'
        articles.append(art)

    count_conn = mysql.connector.connect(**podcast_db_config)
    count_cursor = count_conn.cursor()
    count_cursor.execute("SELECT COUNT(*) FROM podcasts")
    total_count = count_cursor.fetchone()[0]
    count_cursor.close()
    count_conn.close()

    total_pages = -(-total_count // per_page)

    return render_template('index.html', articles=articles,
                           username=session.get('admin_username'),
                           page=page, total_pages=total_pages)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if VALID_USERS.get(user) == pwd:
            session['logged_in'] = True
            session['admin_username'] = user
            return redirect(url_for('index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/code_article/<int:article_id>/', methods=['GET','POST'])
def code_article(article_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor(dictionary=True)

    code_data = None
    if request.method == 'GET':
        cursor.execute("SELECT * FROM codes WHERE article_id = %s", (article_id,))
        code_data = cursor.fetchone()

        if code_data and code_data['status'] == 'in_progress' and code_data['coder'] != session['admin_username']:
            cursor.close()
            conn.close()
            flash(f"This episode is currently being coded by {code_data['coder']}", 'danger')
            return redirect(url_for('index'))

        cursor.execute("""
            INSERT INTO codes (article_id, status, coder)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE status='in_progress', coder=%s
        """, (article_id, 'in_progress', session['admin_username'], session['admin_username']))
        conn.commit()

    elif request.method == 'POST':
        values = {
            'article_id': article_id,
            'topic': request.form.get('topic',''),
            'theme': request.form.get('theme',''),
            'guest_name': request.form.get('guest_name',''),
            'guest_type': request.form.get('guest_type',''),
            'guest_affiliation': request.form.get('guest_affiliation',''),
            'importance': int(request.form.get('importance',0)),
            'notes': request.form.get('notes',''),
            'coder': session['admin_username']
        }
        cursor.execute("""
            INSERT INTO codes (article_id, topic, theme, guest_name, guest_type, guest_affiliation, importance, notes, coder, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, 'done')
            ON DUPLICATE KEY UPDATE
              topic=VALUES(topic), theme=VALUES(theme), guest_name=VALUES(guest_name),
              guest_type=VALUES(guest_type), guest_affiliation=VALUES(guest_affiliation),
              importance=VALUES(importance), notes=VALUES(notes), coder=VALUES(coder), status='done'
        """, tuple(values.values()))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('index'))

    cursor.execute("SELECT * FROM podcasts WHERE id = %s", (article_id,))
    article = cursor.fetchone()
    if code_data:
        article.update(code_data)

    cursor.close()
    conn.close()

    cursor = mysql.connector.connect(**podcast_db_config).cursor()
    cursor.execute("SELECT COUNT(*) FROM podcasts")
    max_id = cursor.fetchone()[0] - 1
    cursor.close()

    return render_template('code_article.html', article=article,
                           article_id=article_id, max_id=max_id)

@app.route('/release_lock/<int:article_id>', methods=['POST'])
def release_lock(article_id):
    if not session.get('logged_in'):
        return '', 204
    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE codes
        SET status = 'pending'
        WHERE article_id = %s AND status = 'in_progress' AND coder = %s
    """, (article_id, session['admin_username']))
    conn.commit()
    cursor.close()
    conn.close()
    return '', 204

@app.route('/view_codes')
def view_codes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM codes WHERE status = 'done' ORDER BY article_id")
    codes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('view_codes.html', codes=codes)

@app.route('/delete_code/<int:code_id>', methods=['POST'])
def delete_code(code_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM codes WHERE article_id=%s", (code_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Entry deleted', 'success')
    return redirect(url_for('view_codes'))

@app.route('/export_codes')
def export_codes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM codes ORDER BY article_id")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    df_export = pd.DataFrame(data)
    buf = BytesIO()
    df_export.to_csv(buf, index=False)
    buf.seek(0)
    fname = datetime.now().strftime("codes_%Y%m%d_%H%M%S.csv")
    return send_file(buf, as_attachment=True, download_name=fname, mimetype='text/csv')

@app.route('/update_coded_status', methods=['POST'])
def update_coded_status():
    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT article_id, coder, importance, notes, status FROM codes")
    status = {r['article_id']: r for r in cursor.fetchall()}
    cursor.close()
    conn.close()
    return jsonify(status)

@app.route('/autocomplete/<field>')
def autocomplete(field):
    allowed_fields = ['topic', 'theme', 'guest_name', 'guest_type', 'guest_affiliation']
    if field not in allowed_fields:
        return jsonify([])  # safeguard

    conn = mysql.connector.connect(**podcast_db_config)
    cursor = conn.cursor()
    cursor.execute(f"SELECT DISTINCT {field} FROM codes WHERE {field} IS NOT NULL AND {field} != ''")
    results = sorted(set(r[0] for r in cursor.fetchall() if r[0]))
    cursor.close()
    conn.close()
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5003)
