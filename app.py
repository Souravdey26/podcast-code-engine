import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pandas as pd
import mysql.connector
import logging
import re

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configuration
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# MySQL configurations
db_config = {
    'user': 'root',
    'password': '@Gultu2024',
    'host': 'localhost',
    'database': 'content_analysis',
}

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Admin credentials
ADMINS = [
    {'username': 'admin1', 'password': 'password1'},
    {'username': 'admin2', 'password': 'password2'}
]

# Function to load the dataset
def load_dataset(file_path):
    print(f"Loading dataset from {file_path}")
    df = pd.read_csv(file_path)
    print(df.dtypes)  # Debug statement to print data types
    print(df.head())  # Print the first few rows of the DataFrame for inspection
    
    # Remove timezone information from the Date column
    if 'Date' in df.columns:
        df['Date'] = df['Date'].apply(lambda x: re.sub(r' [A-Z]{3}$', '', str(x)))
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    # Fill NaN values if necessary
    df = df.fillna('')
    return df

# Function to populate articles table
def populate_articles_table(df):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles")  # Clear existing articles
    for idx, row in df.iterrows():
        cursor.execute("""
            INSERT INTO articles (id, title, content, author, date, link)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (idx, row['Title'], row['Content'], row['Author'], row['Date'], row['Link']))
    conn.commit()
    cursor.close()
    conn.close()
    print("Articles table populated")

# Load the default dataset at startup
try:
    df = load_dataset('C:/Users/deyso/OneDrive/Desktop/Final Datasets AI/hindu_ai_content_final.csv')
    populate_articles_table(df)  # Populate articles table
    print("Dataset loaded and articles table populated successfully at startup")
except Exception as e:
    print(f"Error loading dataset: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        print(f"Attempting login with username: {username} and password: {password}")
        
        # Check if the username and password match any admin credentials
        admin = next((admin for admin in ADMINS if admin['username'] == username and admin['password'] == password), None)
        
        if admin:
            session['logged_in'] = True
            session['admin_username'] = username
            print(f"Logged in as: {username}")
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials. Please try again.')
            print("Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('login'))
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    global df
    if request.method == 'POST':
        print("POST request received for file upload")
        if 'file' not in request.files:
            flash('No file part')
            print("No file part in request")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            print("No selected file")
            return redirect(request.url)
        if file:
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)
                print(f"File saved to {file_path}")
                df = load_dataset(file_path)
                populate_articles_table(df)  # Populate articles table
                flash('File successfully uploaded and dataset loaded')
                print("File successfully uploaded and dataset loaded")
            except Exception as e:
                print(f"Error processing file upload: {e}")
                flash(f"Error processing file upload: {e}")
                return redirect(request.url)
    try:
        # Convert the DataFrame to a list of dictionaries
        articles = df.to_dict(orient='records')
        # Print a sample of articles for debugging
        print(articles[:5])
        return render_template('index.html', articles=articles)
    except Exception as e:
        print(f"Error rendering template: {e}")
        return f"Error rendering template: {e}"

@app.route('/code_article/<int:article_id>/', methods=['GET', 'POST'])
def code_article(article_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        article = df.iloc[article_id]
        print(f"Displaying article ID: {article_id}")
    except Exception as e:
        print(f"Error retrieving article: {e}")
        return f"Error retrieving article: {e}"
    
    if request.method == 'POST':
        try:
            # Collect form data
            coding_data = {
                'article_id': article_id,
                'publication_name': request.form['publication_name'],
                'publication_type': request.form.getlist('publication_type'),
                'date_of_publication': request.form['date_of_publication'],
                'type_of_article': request.form.getlist('type_of_article'),
                'author_name': request.form['author_name'],
                'type_of_author': request.form.getlist('type_of_author'),
                'focus_main_topic': request.form.getlist('focus_main_topic'),
                'actor_mentioned': request.form.getlist('actor_mentioned'),
                'dominant_frame': request.form.getlist('dominant_frame'),
                'benefit_opportunity_frame': request.form.getlist('benefit_opportunity_frame'),
                'risk_threat_frame': request.form.getlist('risk_threat_frame'),
                'ai_ethics': request.form.getlist('ai_ethics'),
                'attribution_of_responsibility': request.form.getlist('attribution_of_responsibility'),
                'human_interest_frame': request.form.getlist('human_interest_frame'),
                'type_of_frame': request.form.getlist('type_of_frame'),
                'tone_of_article': request.form.getlist('tone_of_article')
            }
            print(f"Received coding data for article ID {article_id}: {coding_data}")
            
            # Save the coded data to the MySQL database
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO codes (article_id, publication_name, publication_type, date_of_publication, type_of_article, author_name, type_of_author, focus_main_topic, actor_mentioned, dominant_frame, benefit_opportunity_frame, risk_threat_frame,
                ai_ethics, attribution_of_responsibility, human_interest_frame, type_of_frame, tone_of_article)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                coding_data['article_id'],
                coding_data['publication_name'],
                ', '.join(coding_data['publication_type']),
                coding_data['date_of_publication'],
                ', '.join(coding_data['type_of_article']),
                coding_data['author_name'],
                ', '.join(coding_data['type_of_author']),
                ', '.join(coding_data['focus_main_topic']),
                ', '.join(coding_data['actor_mentioned']),
                ', '.join(coding_data['dominant_frame']),
                ', '.join(coding_data['benefit_opportunity_frame']),
                ', '.join(coding_data['risk_threat_frame']),
                ', '.join(coding_data['ai_ethics']),
                ', '.join(coding_data['attribution_of_responsibility']),
                ', '.join(coding_data['human_interest_frame']),
                ', '.join(coding_data['type_of_frame']),
                ', '.join(coding_data['tone_of_article'])
            ))
            conn.commit()
            cursor.close()
            conn.close()
            print("Data saved to database")
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Error saving data to database: {e}")
            return f"Error saving data to database: {e}"
    
    max_article_id = len(df) - 1
    
    try:
        return render_template('code_article.html', article=article, article_id=article_id, max_article_id=max_article_id)
    except Exception as e:
        print(f"Error rendering template: {e}")
        return f"Error rendering template: {e}"

@app.route('/search')
def search():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    query = request.args.get('query', '').lower()
    results = df[df['Title'].str.lower().str.contains(query, na=False)]
    articles = results.to_dict(orient='records')
    articles = results.to_dict(orient='records')
    return render_template('index.html', articles=articles)

@app.route('/view_codes')
def view_codes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM codes")
        codes = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('view_codes.html', codes=codes)
    except Exception as e:
        print(f"Error retrieving codes from database: {e}")
        return f"Error retrieving codes from database: {e}"

if __name__ == '__main__':
    print("Starting Flask app on port 5002...")
    app.run(debug=True, port=5002)

