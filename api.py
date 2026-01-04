# Version 1.14 - Backdoor Access
import sqlite3
import json
import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, g, session, redirect, url_for, Response, stream_with_context
from werkzeug.security import generate_password_hash, check_password_hash
import stripe
import psycopg2
import psycopg2.extras
from flask_cors import CORS
from dotenv import load_dotenv
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import io

# --- Logging Configuration ---
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from .env file
load_dotenv()

# --- App & Security Configuration ---
app = Flask(__name__, static_folder='static', template_folder='templates')
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
if not SECRET_KEY:
    logging.warning("WARNING: FLASK_SECRET_KEY not set. Sessions will not be persistent across server restarts.")
    SECRET_KEY = 'dev_fallback_secret_key_for_local_testing_only'
app.config['SECRET_KEY'] = SECRET_KEY

# Enable CORS for all domains (simplest fix for Stripe/external scripts)
CORS(app)

# Database Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
# Fix for Render's postgres:// prefix which SQLAlchemy doesn't like
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL if DATABASE_URL else f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Stripe Configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
stripe_publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Price IDs
PRO_PRICE_ID = os.environ.get('STRIPE_PRO_PRICE_ID')
API_BASIC_PRICE_ID = os.environ.get('STRIPE_API_BASIC_PRICE_ID')
API_BUSINESS_PRICE_ID = os.environ.get('STRIPE_API_BUSINESS_PRICE_ID')


def get_db():
    if 'db' not in g:
        if DATABASE_URL:
            try:
                g.db = psycopg2.connect(DATABASE_URL, sslmode='require')
            except Exception as e:
                logging.error(f"Failed to connect to PostgreSQL: {e}")
                raise
        else:
            g.db = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    db_conn = get_db()
    try:
        if DATABASE_URL:
            with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, args)
                db_conn.commit()
                try:
                    rv = cur.fetchall()
                    return (rv[0] if rv else None) if one else rv
                except psycopg2.ProgrammingError:
                    return None
        else:
            cur = db_conn.execute(query, args)
            db_conn.commit()
            rv = cur.fetchall()
            cur.close()
            return (rv[0] if rv else None) if one else rv
    except Exception as e:
        logging.error(f"DATABASE QUERY FAILED: {e}")
        db_conn.rollback()
        raise


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Invalid or missing API Key."}), 401
        api_key = auth_header.split(' ')[1]
        key_record = query_db('SELECT * FROM api_keys WHERE api_key = %s AND is_active = 1' if DATABASE_URL else 'SELECT * FROM api_keys WHERE api_key = ? AND is_active = 1', (api_key,), one=True)
        if not key_record:
            return jsonify({"error": "Invalid or missing API Key."}), 401
        g.api_client_name = key_record['client_name']
        g.api_key_id = key_record['id']
        query_db('UPDATE api_keys SET usage_count = usage_count + 1 WHERE id = %s' if DATABASE_URL else 'UPDATE api_keys SET usage_count = usage_count + 1 WHERE id = ?', (key_record['id'],))
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- Page Routes ---
@app.route('/')
def landing_page(): return render_template('landing.html')
@app.route('/login')
def login_page(): return render_template('login.html')
@app.route('/calculator')
@login_required
def calculator_page(): return render_template('index.html', stripe_publishable_key=stripe_publishable_key)
@app.route('/methodology')
def methodology_page(): return render_template('methodology.html')
@app.route('/contact')
def contact_page(): return render_template('contact.html')
@app.route('/tutorial')
def tutorial_page(): return render_template('tutorial.html')

# --- Auth API ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password are required.'}), 400
    try:
        query_db("INSERT INTO users (username, password, tier) VALUES (%s, %s, 'Free')" if DATABASE_URL else "INSERT INTO users (username, password, tier) VALUES (?, ?, 'Free')", (username, generate_password_hash(password)))
        return jsonify({'message': 'User created successfully.'}), 201
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return jsonify({'error': f"User {username} is already registered."}), 409
        return jsonify({'error': 'An unexpected server error occurred.'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    user = query_db('SELECT * FROM users WHERE username = %s' if DATABASE_URL else 'SELECT * FROM users WHERE username = ?', (username,), one=True)
    if user and check_password_hash(user['password'], password):
        session.clear()
        session['user_id'] = user['id']
        session['tier'] = user['tier']
        session['username'] = user['username']
        session['stripe_customer_id'] = user.get('stripe_customer_id')
        return jsonify({'message': 'Login successful', 'user_id': user['id'], 'tier': user['tier'], 'stripe_customer_id': user.get('stripe_customer_id')})
    return jsonify({'error': 'Invalid username or password.'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/api/session_status')
def session_status():
    if 'user_id' in session:
        # BACKDOOR: Force OGZ to be API_Business
        current_tier = session.get('tier')
        if session.get('username') == 'OGZ':
            current_tier = 'API_Business'
            
        return jsonify({'logged_in': True, 'tier': current_tier, 'username': session.get('username'), 'stripe_customer_id': session.get('stripe_customer_id')})
    return jsonify({'logged_in': False})

# --- Main App API ---
@app.route('/api/predictability_score', methods=['POST'])
@login_required
def get_predictability_score():
    data = request.get_json()
    if 'scores' not in data: return jsonify({'error': '"scores" key is required.'}), 400
    from fsr import calculate_predictability, calculate_deviation
    score_value = calculate_predictability(data['scores'], k=data.get('k', 1.0))
    response_data = {'predictability_score': score_value}
    if 'target_value' in data and data['target_value'] is not None:
        try:
            deviation = calculate_deviation(data['scores'], float(data['target_value']))
            response_data['target_deviation'] = deviation
        except (ValueError, TypeError): pass
    return jsonify(response_data)

@app.route('/api/sliding_window', methods=['POST'])
@login_required
def get_sliding_window():
    # BACKDOOR: Allow OGZ to use sliding window
    current_tier = session.get('tier', 'Free')
    if session.get('username') == 'OGZ':
        current_tier = 'API_Business'

    if current_tier not in ['API_Basic', 'API_Business']:
        return jsonify({'error': 'Sliding Window is a premium feature.'}), 403
    data = request.get_json()
    if 'scores' not in data or 'window_size' not in data: return jsonify({'error': 'Both "scores" and "window_size" are required.'}), 400
    from sliding_window import calculate_sliding_window
    results = calculate_sliding_window(data['scores'], int(data['window_size']), k=data.get('k', 1.0))
    return jsonify({'sliding_window_results': results})

@app.route('/api/analyses', methods=['GET', 'POST'])
@login_required
def handle_analyses():
    user_id = session['user_id']
    if request.method == 'POST':
        data = request.get_json()
        folder_id = data.get('folder_id') if data.get('folder_id') else None
        query_db('INSERT INTO analyses (user_id, name, predictability_score, scores, folder_id, k, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)' if DATABASE_URL else 'INSERT INTO analyses (user_id, name, predictability_score, scores, folder_id, k, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (user_id, data['name'], data['predictability_score'], json.dumps(data['scores']), folder_id, data.get('k', 1.0), data.get('notes', '')))
        return jsonify({'message': 'Analysis saved successfully.'}), 201
    else: # GET
        analyses = query_db('SELECT * FROM analyses WHERE user_id = %s' if DATABASE_URL else 'SELECT * FROM analyses WHERE user_id = ?', (user_id,))
        results = [dict(row) for row in analyses]
        for res in results:
            res['scores'] = json.loads(res['scores'])
        return jsonify({'saved_analyses': results})

@app.route('/api/analysis/<int:analysis_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_single_analysis(analysis_id):
    user_id = session['user_id']
    if request.method == 'GET':
        analysis = query_db('SELECT * FROM analyses WHERE id = %s AND user_id = %s' if DATABASE_URL else 'SELECT * FROM analyses WHERE id = ? AND user_id = ?', (analysis_id, user_id), one=True)
        if not analysis: return jsonify({'error': 'Analysis not found.'}), 404
        result = dict(analysis)
        result['scores'] = json.loads(result['scores'])
        return jsonify(result)
    elif request.method == 'PUT':
        data = request.get_json()
        updates, params = [], []
        for field in ['name', 'scores', 'predictability_score', 'k', 'notes', 'folder_id']:
            if field in data:
                updates.append(f'{field} = %s' if DATABASE_URL else f'{field} = ?')
                value = json.dumps(data[field]) if field == 'scores' else data[field]
                params.append(value)
        if not updates: return jsonify({'error': 'No valid fields to update.'}), 400
        params.extend([analysis_id, user_id])
        query_db(f"UPDATE analyses SET {', '.join(updates)} WHERE id = %s AND user_id = %s" if DATABASE_URL else f"UPDATE analyses SET {', '.join(updates)} WHERE id = ? AND user_id = ?", tuple(params))
        return jsonify({'message': 'Analysis updated successfully.'})
    elif request.method == 'DELETE':
        query_db('DELETE FROM analyses WHERE id = %s AND user_id = %s' if DATABASE_URL else 'DELETE FROM analyses WHERE id = ? AND user_id = ?', (analysis_id, user_id))
        return jsonify({'message': 'Analysis deleted successfully.'})

@app.route('/api/folders', methods=['GET', 'POST'])
@login_required
def handle_folders():
    user_id = session['user_id']
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        if not name: return jsonify({'error': 'Folder name is required.'}), 400
        result = query_db('INSERT INTO folders (user_id, name) VALUES (%s, %s) RETURNING id' if DATABASE_URL else 'INSERT INTO folders (user_id, name) VALUES (?, ?)', (user_id, name), one=True)
        new_id = result['id'] if DATABASE_URL else query_db("select last_insert_rowid() as id", one=True)['id']
        return jsonify({'message': 'Folder created.', 'id': new_id, 'name': name}), 201
    else: # GET
        folders = query_db('SELECT * FROM folders WHERE user_id = %s ORDER BY created_at DESC' if DATABASE_URL else 'SELECT * FROM folders WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        return jsonify({'folders': [dict(row) for row in folders]})

@app.route('/api/folder/<int:folder_id>', methods=['DELETE'])
@login_required
def delete_folder(folder_id):
    user_id = session['user_id']
    query_db('UPDATE analyses SET folder_id = NULL WHERE folder_id = %s AND user_id = %s' if DATABASE_URL else 'UPDATE analyses SET folder_id = NULL WHERE folder_id = ? AND user_id = ?', (folder_id, user_id))
    query_db('DELETE FROM folders WHERE id = %s AND user_id = %s' if DATABASE_URL else 'DELETE FROM folders WHERE id = ? AND user_id = ?', (folder_id, user_id))
    return jsonify({'message': 'Folder deleted successfully.'})

# --- Stripe & B2B API ---
@app.route('/api/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    data = request.get_json() or {}
    plan_type = data.get('plan', 'pro')
    price_id = {'pro': PRO_PRICE_ID, 'api_basic': API_BASIC_PRICE_ID, 'api_business': API_BUSINESS_PRICE_ID}.get(plan_type)
    if not price_id: return jsonify(error={'message': f'Price ID for {plan_type} not configured.'}), 500
    try:
        checkout_session = stripe.checkout.Session.create(line_items=[{'price': price_id, 'quantity': 1}], mode='subscription', allow_promotion_codes=True, success_url=request.host_url + 'calculator?session_id={CHECKOUT_SESSION_ID}', cancel_url=request.host_url + 'calculator', client_reference_id=session['user_id'], metadata={'plan_type': plan_type})
        return jsonify({'url': checkout_session.url})
    except Exception as e:
        return jsonify(error={'message': str(e)}), 500

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return 'Invalid signature', 400
    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        user_id, stripe_customer_id = session_data.get('client_reference_id'), session_data.get('customer')
        plan_type = session_data.get('metadata', {}).get('plan_type', 'pro')
        new_tier = {'pro': 'Pro', 'api_basic': 'API_Basic', 'api_business': 'API_Business'}.get(plan_type, 'Pro')
        if user_id and stripe_customer_id:
            query_db("UPDATE users SET tier = %s, stripe_customer_id = %s WHERE id = %s" if DATABASE_URL else "UPDATE users SET tier = ?, stripe_customer_id = ? WHERE id = ?", (new_tier, stripe_customer_id, int(user_id)))
            logging.info(f"User {user_id} upgraded to {new_tier}.")
    return 'Success', 200

@app.route('/api/create-portal-session', methods=['POST'])
@login_required
def create_portal_session():
    stripe_customer_id = session.get('stripe_customer_id')
    if not stripe_customer_id: return jsonify(error={'message': 'Stripe customer ID not found.'}), 404
    try:
        portal_session = stripe.billing_portal.Session.create(customer=stripe_customer_id, return_url=request.host_url + 'calculator')
        return jsonify({'url': portal_session.url})
    except Exception as e:
        return jsonify(error={'message': str(e)}), 500

@app.route('/api/v1/calculate', methods=['POST'])
@api_key_required
def calculate_api_score():
    data = request.get_json()
    if 'scores' not in data: return jsonify({'error': "'scores' key is required."}), 400
    scores = data['scores']
    if not isinstance(scores, list) or len(scores) < 2: return jsonify({'error': "'scores' must be a list of at least two numbers."}), 400
    try: numeric_scores = [float(s) for s in scores]
    except ValueError: return jsonify({'error': "All scores must be valid numbers."}), 400
    from fsr import calculate_predictability, calculate_deviation
    score_value = calculate_predictability(numeric_scores, k=data.get('k', 1.0))
    response = {'predictability_score': score_value}
    if 'target_value' in data and data['target_value'] is not None:
        try:
            response['target_deviation'] = calculate_deviation(numeric_scores, float(data['target_value']))
        except (ValueError, TypeError): pass
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
