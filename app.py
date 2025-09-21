from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
from datetime import datetime
from flask_socketio import SocketIO, emit, join_room, leave_room
from sentiment_analyzer import sentiment_analyzer
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
socketio = SocketIO(app, cors_allowed_origins="*")

# Database setup (you can replace this with your preferred database)
def init_db():
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Create organizers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS organizers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create events table
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            organizer_id INTEGER,
            date TEXT,
            time TEXT,
            venue TEXT,
            qr_code TEXT UNIQUE,
            organizer_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organizer_id) REFERENCES organizers (id)
        )
    ''')
    
    # Create feedback table
    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            rating INTEGER,
            comment TEXT,
            attendee_name TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    ''')
    
    # Create questions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            question_text TEXT NOT NULL,
            question_type TEXT DEFAULT 'text',
            is_required INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    ''')
    
    # Create answers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            event_id INTEGER,
            answer_text TEXT,
            rating INTEGER,
            attendee_name TEXT,
            attendee_email TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions (id),
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    ''')
    
    # Create live_questions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS live_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            question_text TEXT NOT NULL,
            question_type TEXT DEFAULT 'text',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    ''')
    
    # Create live_answers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS live_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            live_question_id INTEGER,
            event_id INTEGER,
            answer_text TEXT,
            rating INTEGER,
            attendee_name TEXT,
            attendee_email TEXT,
            sentiment TEXT,
            sentiment_score REAL,
            sentiment_confidence REAL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (live_question_id) REFERENCES live_questions (id),
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    ''')
    
    # Remove the test organizer insertion since we'll create accounts on demand
    # c.execute('''
    #     INSERT OR IGNORE INTO organizers (email, password_hash, name) 
    #     VALUES (?, ?, ?)
    # ''', ('admin@test.com', test_password, 'Test Admin'))
    
    conn.commit()
    conn.close()

# Initialize database when app starts
init_db()

# Home page route
@app.route('/')
def home():
    return render_template('index.html')

# Handle organizer login
@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        flash('Please fill in all fields', 'error')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Check if user exists
    c.execute('SELECT id, password_hash, name FROM organizers WHERE email = ?', (email,))
    user = c.fetchone()
    
    if user:
        # User exists, check password
        if check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['user_name'] = user[2]
            session['user_email'] = email
            flash('Login successful!', 'success')
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid password', 'error')
            conn.close()
            return redirect(url_for('home'))
    else:
        # User does not exist → auto-register
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(password)
        c.execute('INSERT INTO organizers (email, password_hash, name) VALUES (?, ?, ?)',
                  (email, password_hash, 'Auto User'))
        conn.commit()
        
        # Fetch the newly created user
        c.execute('SELECT id, name FROM organizers WHERE email = ?', (email,))
        new_user = c.fetchone()
        session['user_id'] = new_user[0]
        session['user_name'] = new_user[1]
        session['user_email'] = email
        flash('Account created automatically and logged in!', 'success')
        conn.close()
        return redirect(url_for('dashboard'))


# Organizer dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('home'))
    
    # Get organizer's events and feedback stats
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Get events for this organizer with comprehensive statistics
    c.execute('''
        SELECT e.id, e.name, e.date, e.time, e.venue, e.qr_code, e.created_at
        FROM events e
        WHERE e.organizer_id = ?
        ORDER BY e.created_at DESC
    ''', (session['user_id'],))
    
    events_data = c.fetchall()
    events = []
    
    for event in events_data:
        event_id = event[0]
        
        # Get regular feedback count and average rating
        c.execute('''
            SELECT COUNT(id) as feedback_count, AVG(rating) as avg_rating
            FROM feedback 
            WHERE event_id = ?
        ''', (event_id,))
        regular_feedback = c.fetchone()
        
        # Get live answers count and average rating
        c.execute('''
            SELECT COUNT(id) as live_count, AVG(rating) as live_avg_rating
            FROM live_answers 
            WHERE event_id = ?
        ''', (event_id,))
        live_feedback = c.fetchone()
        
        # Get sentiment statistics
        c.execute('''
            SELECT 
                COUNT(*) as total_answers,
                SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count,
                SUM(CASE WHEN sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
                AVG(sentiment_score) as avg_sentiment_score,
                AVG(sentiment_confidence) as avg_confidence
            FROM live_answers 
            WHERE event_id = ?
        ''', (event_id,))
        sentiment_stats = c.fetchone()
        
        # Calculate combined statistics
        total_feedback = (regular_feedback[0] or 0) + (live_feedback[0] or 0)
        
        # Calculate weighted average rating
        regular_rating = regular_feedback[1] or 0
        live_rating = live_feedback[1] or 0
        regular_count = regular_feedback[0] or 0
        live_count = live_feedback[0] or 0
        
        if total_feedback > 0:
            avg_rating = ((regular_rating * regular_count) + (live_rating * live_count)) / total_feedback
        else:
            avg_rating = None
        
        events.append({
            'id': event[0],
            'name': event[1],
            'date': event[2],
            'time': event[3],
            'venue': event[4],
            'qr_code': event[5],
            'created_at': event[6],
            'feedback_count': total_feedback,
            'avg_rating': avg_rating,
            'regular_feedback_count': regular_feedback[0] or 0,
            'live_feedback_count': live_feedback[0] or 0,
            'sentiment_stats': {
                'total_answers': sentiment_stats[0] or 0,
                'positive_count': sentiment_stats[1] or 0,
                'negative_count': sentiment_stats[2] or 0,
                'neutral_count': sentiment_stats[3] or 0,
                'avg_sentiment_score': sentiment_stats[4] or 0,
                'avg_confidence': sentiment_stats[5] or 0
            }
        })
    
    conn.close()
    
    return render_template('dashboard.html', events=events, user_name=session.get('user_name'))



# Create new event
@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        event_name = request.form.get('event_name')
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        venue = request.form.get('venue')
        organizer_name = request.form.get('organizer_name')
        
        if all([event_name, event_date, event_time, venue, organizer_name]):
            # Generate a simple QR code identifier (in production, use a proper QR code library)
            import uuid
            qr_code = str(uuid.uuid4())[:8].upper()
            
            conn = sqlite3.connect('feedback_portal.db')
            c = conn.cursor()
            c.execute('''
                INSERT INTO events (name, date, time, venue, organizer_name, organizer_id, qr_code)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (event_name, event_date, event_time, venue, organizer_name, session['user_id'], qr_code))
            conn.commit()
            conn.close()
            
            flash(f'Event "{event_name}" created successfully! QR Code: {qr_code}', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Please fill in all fields', 'error')
    
    # Pre-fill organizer name with user's name
    return render_template('create_event.html', user_name=session.get('user_name', ''))

# QR Scanner page
@app.route('/scanner')
def qr_scanner():
    return render_template('qr_scanner.html')

# QR code event page - shows questions for attendees
@app.route('/event/<qr_code>')
def event_page(qr_code):
    # Get event details from QR code
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    c.execute('SELECT id, name, date, time, venue, organizer_name FROM events WHERE qr_code = ?', (qr_code,))
    event = c.fetchone()
    
    if not event:
        conn.close()
        flash('Invalid QR code. Please check the code and try again.', 'error')
        return redirect(url_for('qr_scanner'))
    
    conn.close()
    
    return render_template('event_page.html', event=event, qr_code=qr_code)

# Submit answers from event page
@app.route('/submit_answers', methods=['POST'])
def submit_answers():
    event_id = request.form.get('event_id')
    attendee_name = request.form.get('attendee_name', '')
    attendee_email = request.form.get('attendee_email', '')
    
    if not event_id:
        flash('Invalid event', 'error')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Get all questions for this event
    c.execute('SELECT id, question_type FROM questions WHERE event_id = ?', (event_id,))
    questions = c.fetchall()
    
    # Process each answer
    for question_id, question_type in questions:
        answer_key = f'answer_{question_id}'
        answer_value = request.form.get(answer_key)
        
        if answer_value:  # Only save non-empty answers
            if question_type == 'rating':
                c.execute('''
                    INSERT INTO answers (question_id, event_id, rating, attendee_name, attendee_email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (question_id, event_id, int(answer_value), attendee_name, attendee_email))
            else:
                c.execute('''
                    INSERT INTO answers (question_id, event_id, answer_text, attendee_name, attendee_email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (question_id, event_id, answer_value, attendee_name, attendee_email))
    
    conn.commit()
    conn.close()
    
    return render_template('thank_you.html')

# Event management page for organizers
@app.route('/manage_event/<int:event_id>')
def manage_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Check if this event belongs to the logged-in organizer
    c.execute('''
        SELECT id, name, date, time, venue, organizer_name, qr_code 
        FROM events 
        WHERE id = ? AND organizer_id = ?
    ''', (event_id, session['user_id']))
    event = c.fetchone()
    
    if not event:
        conn.close()
        flash('Event not found or access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get questions for this event
    c.execute('''
        SELECT id, question_text, question_type, is_required, created_at
        FROM questions 
        WHERE event_id = ? 
        ORDER BY created_at
    ''', (event_id,))
    questions = c.fetchall()
    
    # Get response count
    c.execute('SELECT COUNT(DISTINCT attendee_email) FROM answers WHERE event_id = ?', (event_id,))
    response_count = c.fetchone()[0]
    
    conn.close()
    
    return render_template('manage_event.html', event=event, questions=questions, response_count=response_count)

# Add question to event
@app.route('/add_question/<int:event_id>', methods=['POST'])
def add_question(event_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    question_text = request.form.get('question_text')
    question_type = request.form.get('question_type', 'text')
    is_required = 1 if request.form.get('is_required') else 0
    
    if not question_text:
        flash('Question text is required', 'error')
        return redirect(url_for('manage_event', event_id=event_id))
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Verify event belongs to organizer
    c.execute('SELECT id FROM events WHERE id = ? AND organizer_id = ?', (event_id, session['user_id']))
    if not c.fetchone():
        conn.close()
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Add question
    c.execute('''
        INSERT INTO questions (event_id, question_text, question_type, is_required)
        VALUES (?, ?, ?, ?)
    ''', (event_id, question_text, question_type, is_required))
    
    conn.commit()
    conn.close()
    
    flash('Question added successfully!', 'success')
    return redirect(url_for('manage_event', event_id=event_id))

# View answers for an event
@app.route('/view_answers/<int:event_id>')
def view_answers(event_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Check if this event belongs to the logged-in organizer
    c.execute('SELECT name FROM events WHERE id = ? AND organizer_id = ?', 
              (event_id, session['user_id']))
    event = c.fetchone()
    
    if not event:
        conn.close()
        flash('Event not found or access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get all answers with question details
    c.execute('''
        SELECT q.question_text, q.question_type, a.answer_text, a.rating,
               a.attendee_name, a.attendee_email, a.submitted_at
        FROM answers a
        JOIN questions q ON a.question_id = q.id
        WHERE a.event_id = ?
        ORDER BY a.submitted_at DESC, q.created_at
    ''', (event_id,))
    
    answers = c.fetchall()
    
    # Group answers by submission
    submissions = {}
    for answer in answers:
        key = f"{answer[4]}_{answer[5]}_{answer[6]}"  # name_email_time
        if key not in submissions:
            submissions[key] = {
                'attendee_name': answer[4],
                'attendee_email': answer[5],
                'submitted_at': answer[6],
                'answers': []
            }
        submissions[key]['answers'].append({
            'question': answer[0],
            'type': answer[1],
            'answer': answer[2] if answer[1] != 'rating' else answer[3]
        })
    
    conn.close()
    
    return render_template('view_answers.html', 
                         event_name=event[0], 
                         submissions=submissions.values(),
                         event_id=event_id)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('home'))

# Generate QR code for event
@app.route('/generate_qr/<int:event_id>')
def generate_qr(event_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Check if event belongs to organizer
    c.execute('SELECT qr_code, name FROM events WHERE id = ? AND organizer_id = ?', 
              (event_id, session['user_id']))
    event = c.fetchone()
    
    if not event:
        conn.close()
        flash('Event not found or access denied', 'error')
        return redirect(url_for('dashboard'))
    
    conn.close()
    
    # Return QR code data as JSON
    return jsonify({
        'qr_code': event[0],
        'event_name': event[1],
        'event_url': url_for('event_page', qr_code=event[0], _external=True)
    })

# API endpoint for QR scanner validation
@app.route('/api/validate_qr/<qr_code>')
def validate_qr(qr_code):
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    c.execute('SELECT id, name FROM events WHERE qr_code = ?', (qr_code,))
    event = c.fetchone()
    conn.close()
    
    if event:
        return jsonify({
            'valid': True,
            'event_id': event[0],
            'event_name': event[1],
            'event_url': url_for('event_page', qr_code=qr_code, _external=True)
        })
    else:
        return jsonify({'valid': False}), 404

# Live Question Management Routes
@app.route('/live_questions/<int:event_id>')
def live_questions(event_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    # Debug: Print session info
    print(f"DEBUG: Session user_id: {session.get('user_id')}")
    print(f"DEBUG: Session user_name: {session.get('user_name')}")
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Check if event belongs to organizer
    c.execute('SELECT name FROM events WHERE id = ? AND organizer_id = ?', 
              (event_id, session['user_id']))
    event = c.fetchone()
    
    print(f"DEBUG: Event lookup result: {event}")
    
    if not event:
        conn.close()
        flash('Event not found or access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get live questions
    c.execute('''
        SELECT id, question_text, question_type, is_active, created_at
        FROM live_questions 
        WHERE event_id = ? 
        ORDER BY created_at DESC
    ''', (event_id,))
    live_questions = c.fetchall()
    
    # Debug: Print questions to console
    print(f"DEBUG: Event ID: {event_id}")
    print(f"DEBUG: Live questions count: {len(live_questions)}")
    print(f"DEBUG: Live questions data: {live_questions}")
    
    # Get live answers with sentiment analysis
    c.execute('''
        SELECT la.id, la.answer_text, la.rating, la.attendee_name, 
               la.sentiment, la.sentiment_score, la.sentiment_confidence, la.submitted_at,
               lq.question_text
        FROM live_answers la
        JOIN live_questions lq ON la.live_question_id = lq.id
        WHERE la.event_id = ?
        ORDER BY la.submitted_at DESC
    ''', (event_id,))
    live_answers = c.fetchall()
    
    conn.close()
    
    return render_template('live_questions.html', 
                         event_id=event_id, 
                         event_name=event[0],
                         live_questions=live_questions,
                         live_answers=live_answers)

@app.route('/add_live_question/<int:event_id>', methods=['POST'])
def add_live_question(event_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    question_text = request.form.get('question_text')
    question_type = request.form.get('question_type', 'text')
    
    if not question_text:
        return jsonify({'success': False, 'message': 'Question text is required'})
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Verify event belongs to organizer
    c.execute('SELECT id FROM events WHERE id = ? AND organizer_id = ?', 
              (event_id, session['user_id']))
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'message': 'Access denied'})
    
    # Add live question
    c.execute('''
        INSERT INTO live_questions (event_id, question_text, question_type)
        VALUES (?, ?, ?)
    ''', (event_id, question_text, question_type))
    
    question_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Emit to all connected clients for this event
    socketio.emit('new_live_question', {
        'question_id': question_id,
        'question_text': question_text,
        'question_type': question_type,
        'event_id': event_id
    }, room=f'event_{event_id}')
    
    return jsonify({'success': True, 'message': 'Live question added successfully'})

@app.route('/submit_live_answer', methods=['POST'])
def submit_live_answer():
    live_question_id = request.form.get('live_question_id')
    event_id = request.form.get('event_id')
    answer_text = request.form.get('answer_text', '')
    rating = request.form.get('rating')
    attendee_name = request.form.get('attendee_name', '')
    attendee_email = request.form.get('attendee_email', '')
    
    if not live_question_id or not event_id:
        return jsonify({'success': False, 'message': 'Invalid request'})
    
    # Analyze sentiment
    sentiment_result = sentiment_analyzer.predict_sentiment(answer_text)
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Save live answer
    c.execute('''
        INSERT INTO live_answers (live_question_id, event_id, answer_text, rating, 
                                attendee_name, attendee_email, sentiment, sentiment_score, sentiment_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (live_question_id, event_id, answer_text, rating, attendee_name, attendee_email,
          sentiment_result['sentiment'], sentiment_result['score'], sentiment_result['confidence']))
    
    answer_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Emit to all connected clients for this event
    socketio.emit('new_live_answer', {
        'answer_id': answer_id,
        'answer_text': answer_text,
        'rating': rating,
        'attendee_name': attendee_name,
        'sentiment': sentiment_result['sentiment'],
        'sentiment_score': sentiment_result['score'],
        'sentiment_confidence': sentiment_result['confidence'],
        'event_id': event_id,
        'live_question_id': live_question_id
    }, room=f'event_{event_id}')
    
    return jsonify({'success': True, 'message': 'Answer submitted successfully'})

@app.route('/get_live_questions/<int:event_id>')
def get_live_questions(event_id):
    """Get live questions for attendees (no authentication required) - limited to top 5 most recent"""
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Get active live questions (all)
    c.execute('''
        SELECT id, question_text, question_type, created_at
        FROM live_questions 
        WHERE event_id = ? AND is_active = 1
        ORDER BY created_at DESC
    ''', (event_id,))
    questions = c.fetchall()
    
    conn.close()
    
    return jsonify({
        'questions': [
            {
                'question_id': q[0],
                'question_text': q[1],
                'question_type': q[2],
                'created_at': q[3]
            } for q in questions
        ]
    })

@app.route('/live_feedback/<int:event_id>')
def live_feedback(event_id):
    """Live feedback page for attendees"""
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Get event details
    c.execute('SELECT name FROM events WHERE id = ?', (event_id,))
    event = c.fetchone()
    
    if not event:
        conn.close()
        flash('Event not found', 'error')
        return redirect(url_for('home'))
    
    conn.close()
    
    return render_template('live_feedback.html', 
                         event_id=event_id, 
                         event_name=event[0])

@app.route('/get_sentiment_analysis/<int:event_id>')
def get_sentiment_analysis(event_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('feedback_portal.db')
    c = conn.cursor()
    
    # Check if event belongs to organizer
    c.execute('SELECT name FROM events WHERE id = ? AND organizer_id = ?', 
              (event_id, session['user_id']))
    event = c.fetchone()
    
    if not event:
        conn.close()
        return jsonify({'error': 'Access denied'})
    
    # Get all live answers for sentiment analysis
    c.execute('''
        SELECT answer_text, sentiment, sentiment_score, sentiment_confidence
        FROM live_answers 
        WHERE event_id = ?
    ''', (event_id,))
    answers = c.fetchall()
    
    conn.close()
    
    if not answers:
        return jsonify({
            'total_answers': 0,
            'sentiment_counts': {'positive': 0, 'negative': 0, 'neutral': 0},
            'sentiment_percentages': {'positive': 0, 'negative': 0, 'neutral': 0},
            'average_score': 0,
            'average_confidence': 0
        })
    
    # Calculate sentiment statistics
    sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
    total_score = 0
    total_confidence = 0
    
    for answer in answers:
        sentiment = answer[1] or 'neutral'
        sentiment_counts[sentiment] += 1
        total_score += answer[2] or 0
        total_confidence += answer[3] or 0
    
    total_answers = len(answers)
    
    return jsonify({
        'total_answers': total_answers,
        'sentiment_counts': sentiment_counts,
        'sentiment_percentages': {
            'positive': round((sentiment_counts['positive'] / total_answers) * 100, 1),
            'negative': round((sentiment_counts['negative'] / total_answers) * 100, 1),
            'neutral': round((sentiment_counts['neutral'] / total_answers) * 100, 1)
        },
        'average_score': round(total_score / total_answers, 3),
        'average_confidence': round(total_confidence / total_answers, 3)
    })

# WebSocket event handlers
@socketio.on('join_event')
def on_join_event(data):
    event_id = data['event_id']
    join_room(f'event_{event_id}')
    emit('status', {'msg': f'Joined event {event_id}'})

@socketio.on('leave_event')
def on_leave_event(data):
    event_id = data['event_id']
    leave_room(f'event_{event_id}')
    emit('status', {'msg': f'Left event {event_id}'})

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    socketio.run(app, debug=True)