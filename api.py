# Version 1.70 - Fixed Stability Ticker paths
import sqlite3
import json
import os
import uuid
from functools import wraps
from flask import Flask, request, jsonify, render_template, g, session, redirect, url_for, Response, stream_with_context, send_from_directory, make_response
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
import re
from flasgger import Swagger
import time
from datetime import datetime
from sqlalchemy import inspect, text
import requests # Added for Moltbook verification

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()
import threading
from collections import deque

# --- Network Stability State for Ticker/HUB ---
class NetworkState:
    def __init__(self):
        self.latency_history = deque(maxlen=100)
        self.last_ping = 0.0
        self.p_score = 100.0  # We'll use 0-100 to match your branding

network_status = NetworkState()

def ping_worker():
    """Background thread to ping Google and update state."""
    while True:
        try:
            # High-performance ping extraction
            # -n 1 for Windows (VS), use -c 1 if you move to Linux/Render
            output = subprocess.check_output(["ping", "-n", "1", "8.8.8.8"]).decode()
            match = re.search(r"time[=<]\s*([\d.]+)\s*ms", output)
            
            if match:
                current_ms = float(match.group(1))
                network_status.latency_history.append(current_ms)
                network_status.last_ping = current_ms
                
                # Calculate Stability (P-Score) using Coefficient of Variation
                if len(network_status.latency_history) > 5:
                    import numpy as np
                    cv = np.std(network_status.latency_history) / np.mean(network_status.latency_history)
                    # Convert to a 0-100 score: Higher CV = Lower Score
                    network_status.p_score = max(0, min(100, (1 - cv) * 100))
            
            time.sleep(1) # Ping every second for the 24/7 ticker
        except Exception as e:
            logging.error(f"Ping Worker Error: {e}")
            time.sleep(5)

# Start the background thread immediately
threading.Thread(target=ping_worker, daemon=True).start()
# --- App & Security Configuration ---
app = Flask(__name__, static_folder='static', template_folder='templates')
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
if not SECRET_KEY:
    logging.warning("WARNING: FLASK_SECRET_KEY not set. Sessions will not be persistent across server restarts.")
    SECRET_KEY = 'dev_fallback_secret_key_for_local_testing_only'
app.config['SECRET_KEY'] = SECRET_KEY

# Enable CORS for all domains
CORS(app)

# --- Constants ---
MAX_API_SCORES_LENGTH = 5000
MAX_API_WINDOW_SIZE = 1000

# --- Swagger Configuration ---
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Predictability API",
        "description": f"""
# The FICO Score for Data Reliability
Stop gambling on volatility. This API quantifies the **consistency** and **stability** of any time-series dataset using the **Predictability Score™** (0-100).

**Need an API Key?** Get one instantly at [predictability-api.com/calculator](https://predictability-api.com/calculator) (requires Business tier).

## 🚀 Changelog
*   **v1.2 (Current):** Added **Moltbook Identity** support for AI Agents.
*   **v1.1:** Added `Sliding Window` endpoint for drift detection.
*   **v1.0:** Initial Launch. Core Predictability Score and Target Deviation.

## 🤖 For AI Agents (Moltbook)
If you are an autonomous agent, you can authenticate using your Moltbook Identity Token.
1. Get your token from Moltbook.
2. Send it in the `X-Moltbook-Identity` header.
3. No API key required for verified agents (Rate limits apply).

## ⚠️ Limits
*   **Max Data Points:** {MAX_API_SCORES_LENGTH}
*   **Max Sliding Window Size:** {MAX_API_WINDOW_SIZE}
        """,
        "version": "1.2.0",
        "contact": {
            "email": "support@predictability-api.com",
            "url": "https://predictability-api.com"
        }
    },
    "schemes": [
        "https",
        "http"
    ],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Enter your API Key as: Bearer <YOUR_API_KEY>"
        },
        "Moltbook": {
            "type": "apiKey",
            "name": "X-Moltbook-Identity",
            "in": "header",
            "description": "Moltbook Identity Token"
        }
    }
}

swagger = Swagger(app, template=swagger_template)

# Database Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    SQLALCHEMY_DATABASE_URI = DATABASE_URL if DATABASE_URL else f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')}"

app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Stripe Configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
stripe_publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Price IDs (Updated to match Junie's convention)
PRO_PRICE_ID = os.environ.get('STRIPE_PRICE_ID_PRO') or os.environ.get('STRIPE_PRO_PRICE_ID')
API_BASIC_PRICE_ID = os.environ.get('STRIPE_PRICE_ID_API_BASIC') or os.environ.get('STRIPE_API_BASIC_PRICE_ID')
API_BUSINESS_PRICE_ID = os.environ.get('STRIPE_PRICE_ID_API_BUSINESS') or os.environ.get('STRIPE_API_BUSINESS_PRICE_ID')

# Moltbook Configuration
MOLTBOOK_APP_KEY = os.environ.get('MOLTBOOK_APP_KEY')

# --- Rate Limiting (In-Memory for now) ---
RATE_LIMITS = {}
RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_MAX_REQUESTS = 1000  # 1000 requests per hour

@app.before_request
def log_request_info():
    real_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    logging.info(f"Request: {request.method} {request.path} from IP: {real_ip} - Agent: {request.user_agent.string}")

def check_rate_limit(api_key_id):
    current_time = time.time()
    if api_key_id not in RATE_LIMITS:
        RATE_LIMITS[api_key_id] = {'count': 1, 'reset_time': current_time + RATE_LIMIT_WINDOW}
        return True
    
    limit_data = RATE_LIMITS[api_key_id]
    
    if current_time > limit_data['reset_time']:
        limit_data['count'] = 1
        limit_data['reset_time'] = current_time + RATE_LIMIT_WINDOW
        return True
    
    if limit_data['count'] >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    limit_data['count'] += 1
    return True

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
    # Auto-convert %s to ? if you happen to fall back to SQLite locally
    if not DATABASE_URL:
        query = query.replace('%s', '?')
        
    try:
        if DATABASE_URL:
            # THIS IS THE KEY: RealDictCursor maps columns to names
            with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, args)
                db_conn.commit()
                try:
                    rv = cur.fetchall()
                except psycopg2.ProgrammingError:
                    return None
        else:
            # SQLite mapping
            cur = db_conn.execute(query, args)
            db_conn.commit()
            rv = [dict(row) for row in cur.fetchall()]
            cur.close()

        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        logging.error(f"Mapping Error: {e}")
        db_conn.rollback()
        return None
    except Exception as e:
        logging.error(f"DATABASE QUERY FAILED: {e}")
        db_conn.rollback()
        raise

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            # If the request is an API call (starts with /api/), return JSON error
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required. Please log in.'}), 401
            # Otherwise, redirect to login page
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# --- Moltbook Middleware ---
def moltbook_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Check for Moltbook Header
        token = request.headers.get('X-Moltbook-Identity')
        
        if not token:
            # Fallback to standard API Key check if no Moltbook token
            return api_key_required(f)(*args, **kwargs)

        # 2. Verify Token with Moltbook
        if not MOLTBOOK_APP_KEY:
            logging.error("MOLTBOOK_APP_KEY not set in environment.")
            return jsonify({"error": "Moltbook integration not configured on server."}), 500

        try:
            verify_response = requests.post(
                "https://moltbook.com/api/v1/agents/verify-identity",
                headers={"X-Moltbook-App-Key": MOLTBOOK_APP_KEY},
                json={"token": token},
                timeout=5
            )
            
            if verify_response.status_code != 200:
                return jsonify({"error": "Moltbook verification failed", "details": verify_response.text}), 401
            
            data = verify_response.json()
            
            if not data.get("valid"):
                return jsonify({"error": "Invalid Moltbook token", "code": data.get("error")}), 401
            
            # 3. Attach Agent to Request Context
            g.agent = data.get("agent")
            g.api_client_name = f"Moltbook Agent: {g.agent['name']} ({g.agent['id']})"
            
            # Rate Limit Check for Agents (Shared Pool for now)
            # In production, you'd track usage by g.agent['id']
            
            return f(*args, **kwargs)

        except requests.exceptions.RequestException as e:
            logging.error(f"Moltbook API Error: {e}")
            return jsonify({"error": "Failed to contact Moltbook verification server."}), 503

    return decorated_function

def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If g.agent is already set by Moltbook middleware, skip API key check
        if hasattr(g, 'agent') and g.agent:
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Invalid or missing API Key."}), 401
        api_key = auth_header.split(' ')[1]
        
        # --- DEMO BYPASS ---
        if api_key == "DEMO_KEY":
            referrer = request.headers.get("Referer")
            if referrer and ('localhost' in referrer or 'predictability-api.com' in referrer):
                return f(*args, **kwargs)
            else:
                return jsonify({"error": "DEMO_KEY is only for use on the official demo page."}), 403
        # -------------------

        key_record = query_db('SELECT * FROM api_keys WHERE api_key = %s AND is_active = 1' if DATABASE_URL else 'SELECT * FROM api_keys WHERE api_key = ? AND is_active = 1', (api_key,), one=True)
        if not key_record:
            return jsonify({"error": "Invalid or missing API Key."}), 401
        
        if not check_rate_limit(key_record['id']):
            return jsonify({"error": "Rate limit exceeded. Limit is 1000 requests per hour."}), 429

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
    csp = {
        "default-src": "'self'",
        "script-src": ["'self'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://js.stripe.com", "https://www.googletagmanager.com", "https://www.clarity.ms", "https://*.clarity.ms", "'unsafe-inline'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "https://www.clarity.ms", "https://*.clarity.ms", "https://i.bing.com"],
        "connect-src": ["'self'", "https://api.stripe.com", "https://www.clarity.ms", "https://*.clarity.ms", "https://*.c.bing.com", "https://*.bing.com", "https://www.google-analytics.com", "https://moltbook.com", "https://docs.google.com", "https://*.googleusercontent.com"],
        "frame-src": ["https://js.stripe.com", "https://www.googletagmanager.com", "https://www.clarity.ms"]
    }
    csp_string = "; ".join([f"{key} {' '.join(value) if isinstance(value, list) else value}" for key, value in csp.items()])
    response.headers["Content-Security-Policy"] = csp_string
    return response

# --- PWA & SEO Routes ---
@app.route('/manifest.json')
def serve_manifest(): return send_from_directory('.', 'manifest.json')
@app.route('/service-worker.js')
def serve_sw(): return send_from_directory('.', 'service-worker.js')
@app.route('/robots.txt')
def serve_robots(): return send_from_directory('.', 'robots.txt')
@app.route('/llms.txt')
def serve_llms(): return send_from_directory('.', 'llms.txt')
@app.route('/favicon.ico')
def favicon(): return send_from_directory(os.path.join(app.root_path, 'static', 'images'), 'brand_logo.png', mimetype='image/vnd.microsoft.icon')
@app.route('/apple-touch-icon.png')
@app.route('/apple-touch-icon-precomposed.png')
def serve_apple_icon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'images'), 'brand_logo.png', mimetype='image/png')

@app.route('/sitemap.xml')
def sitemap():
    pages = []
    # Loop through rules as you already do
    for rule in app.url_map.iter_rules():
        if not rule.arguments and "GET" in rule.methods:
            # Add the beacon with custom priority in the template
            pages.append(url_for(rule.endpoint, _external=True))
    
    # Pass a specific 'high_priority_page' to the template
    return Response(render_template('sitemap_template.xml', 
                                   pages=pages, 
                                   beacon_url=url_for('agent_beacon', _external=True),
                                   lastmod=datetime.now().strftime('%Y-%m-%d')), 
                    mimetype='application/xml')

# --- Page Routes ---
@app.route('/')
def landing_page(): return render_template('landing.html')
@app.route('/login')
def login_page(): return render_template('login.html')
@app.route('/calculator')
def calculator_page(): return render_template('index.html', stripe_publishable_key=stripe_publishable_key)
@app.route('/methodology')
def methodology_page(): return render_template('methodology.html')
@app.route('/technical-validation')
def technical_validation_page(): return render_template('technical_validation.html')
@app.route('/contact')
def contact_page(): return render_template('contact.html')
@app.route('/tutorial')
def tutorial_page(): return render_template('tutorial.html')
@app.route('/privacy')
def privacy_page(): return render_template('privacy.html')
@app.route('/terms')
def terms_page(): return render_template('terms.html')
@app.route('/one_pager')
def one_pager():
    return render_template('one_pager.html')
@app.route('/demo/industrial')
def demo_industrial_page(): return render_template('demo_industrial.html')
@app.route('/demo/sports')
def demo_sports_page(): return render_template('demo_sports.html')
@app.route('/stream-overlay')
def stream_overlay_page(): return render_template('stream_overlay.html') # New Route
@app.route('/debug_overlay')
def debug_overlay_page(): return render_template('debug_overlay.html')
@app.route('/about')
@app.route('/about-us')
@app.route('/team')
@app.route('/our-team')
def redirect_to_home(): return redirect(url_for('landing_page'))
@app.route('/contact-us')
@app.route('/support')
def redirect_to_contact(): return redirect(url_for('contact_page'))

# --- Stability Ticker Routes ---
@app.route('/ticker')
def ticker_generator_page():
    return render_template('ticker_generator.html')

@app.route('/render-ticker')
def ticker_render_page():
    return render_template('ticker_render.html')

# --- New Routes for Discovery ---
@app.route('/docs')
@app.route('/apidocs')
def docs_redirect():
    """Redirects /docs to the Swagger UI"""
    return redirect('/apidocs')

@app.route('/sdk')
def sdk_redirect():
    """Redirects /sdk to the contact page or a specific SDK page if you have one"""
    # Since you don't have a public SDK page yet, pointing to contact or docs is best
    return redirect('/contact')

# --- Admin Routes ---
@app.route('/api/v1/network/stability', methods=['GET'])
def get_network_stability():
    """
    Endpoint for the Twitch Dashboard and HUB to pull live network consistency.
    """
    return jsonify({
        "ticker": "STABILITY-NET",
        "latency_ms": network_status.last_ping,
        "p_score": round(network_status.p_score, 2),
        "history_count": len(network_status.latency_history),
        "status": "Institutional" if network_status.p_score > 85 else "Volatility Detected"
    })

@app.route('/admin/users')
@login_required
def admin_users():
    if session.get('username') != 'OGZ': return "Access Denied. Admin only.", 403
    try:
        # Fetch users AND their active API key (if any)
        query = """
            SELECT u.id, u.username, u.tier, u.stripe_customer_id, 
                   k.api_key, k.usage_count
            FROM users u
            LEFT JOIN api_keys k ON u.id = k.user_id AND k.is_active = 1
            ORDER BY u.id DESC
        """
        users = query_db(query)
    except Exception as e: return f"Database Error: {e}", 500
    return render_template('admin_users.html', users=users)

@app.route('/admin/set_tier/<username>/<tier>')
@login_required
def admin_set_tier(username, tier):
    if session.get('username') != 'OGZ': return "Access Denied. Admin only.", 403
    allowed_tiers = ['Free', 'Pro', 'API_Basic', 'API_Business']
    if tier not in allowed_tiers: return f"Invalid tier. Allowed tiers are: {', '.join(allowed_tiers)}", 400
    try:
        query_db("UPDATE users SET tier = %s WHERE username = %s", (tier, username))
        return f"Success: User '{username}' has been updated to tier '{tier}'."
    except Exception as e: return f"An error occurred: {e}", 500

@app.route('/admin/generate_key/<int:user_id>')
@login_required
def admin_generate_key(user_id):
    if session.get('username') != 'OGZ': return "Access Denied.", 403
    new_key = str(uuid.uuid4())
    try:
        # Deactivate old keys
        query_db('UPDATE api_keys SET is_active = 0 WHERE user_id = %s' if DATABASE_URL else 'UPDATE api_keys SET is_active = 0 WHERE user_id = ?', (user_id,))
        # Insert new key
        query_db('INSERT INTO api_keys (user_id, api_key, client_name, is_active) VALUES (%s, %s, %s, 1)' if DATABASE_URL else 'INSERT INTO api_keys (user_id, api_key, client_name, is_active) VALUES (?, ?, ?, 1)', (user_id, new_key, "Admin Generated Key"))
        return redirect(url_for('admin_users'))
    except Exception as e: return f"Error: {e}", 500

@app.route('/admin/revoke_key/<int:user_id>')
@login_required
def admin_revoke_key(user_id):
    if session.get('username') != 'OGZ': return "Access Denied.", 403
    try:
        query_db('UPDATE api_keys SET is_active = 0 WHERE user_id = %s' if DATABASE_URL else 'UPDATE api_keys SET is_active = 0 WHERE user_id = ?', (user_id,))
        return redirect(url_for('admin_users'))
    except Exception as e: return f"Error: {e}", 500

# --- Auth API ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    if not username or not password: return jsonify({'error': 'Username and password are required.'}), 400
    recovery_key = str(uuid.uuid4()).upper()
    recovery_key_hash = generate_password_hash(recovery_key)
    try:
        query_db("INSERT INTO users (username, password, tier, recovery_key_hash) VALUES (%s, %s, 'Free', %s)" if DATABASE_URL else "INSERT INTO users (username, password, tier, recovery_key_hash) VALUES (?, ?, 'Free', ?)", (username, generate_password_hash(password), recovery_key_hash))
        return jsonify({'message': 'User created successfully.', 'recovery_key': recovery_key}), 201
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower(): return jsonify({'error': f"User {username} is already registered."}), 409
        return jsonify({'error': 'An unexpected server error occurred.'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # This line uses the %s for Postgres and the (username,) mapping
    user = query_db('SELECT * FROM users WHERE username = %s', (username,), one=True)

    if user and check_password_hash(user['password'], password):
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        # This is the most important part for your $20 users:
        session['tier'] = user.get('tier', 'Free') 
        return jsonify({'message': 'Login successful', 'tier': session['tier']})
    
    return jsonify({'error': 'Invalid credentials'}), 401
@app.route('/api/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    username, recovery_key, new_password = data.get('username'), data.get('recovery_key'), data.get('new_password')
    if not username or not recovery_key or not new_password: return jsonify({'error': 'All fields are required.'}), 400
    user = query_db('SELECT * FROM users WHERE username = %s' if DATABASE_URL else 'SELECT * FROM users WHERE username = ?', (username,), one=True)
    if not user: return jsonify({'error': 'User not found.'}), 404
    if not user.get('recovery_key_hash'): return jsonify({'error': 'No recovery key set for this user.'}), 400
    if check_password_hash(user['recovery_key_hash'], recovery_key):
        new_hash = generate_password_hash(new_password)
        query_db('UPDATE users SET password = %s WHERE id = %s' if DATABASE_URL else 'UPDATE users SET password = ? WHERE id = ?', (new_hash, user['id']))
        return jsonify({'message': 'Password reset successfully. Please login.'}), 200
    else: return jsonify({'error': 'Invalid Recovery Key.'}), 401

@app.route('/api/change_password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    old_password, new_password = data.get('old_password'), data.get('new_password')
    user_id = session['user_id']
    if not old_password or not new_password: return jsonify({'error': 'Both old and new passwords are required.'}), 400
    user = query_db('SELECT * FROM users WHERE id = %s' if DATABASE_URL else 'SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not user or not check_password_hash(user['password'], old_password): return jsonify({'error': 'Incorrect old password.'}), 401
    new_hash = generate_password_hash(new_password)
    query_db('UPDATE users SET password = %s WHERE id = %s' if DATABASE_URL else 'UPDATE users SET password = ? WHERE id = ?', (new_hash, user_id))
    return jsonify({'message': 'Password changed successfully.'}), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/api/session_status')
def session_status():
    if 'user_id' in session: return jsonify({'logged_in': True, 'tier': session.get('tier'), 'username': session.get('username'), 'stripe_customer_id': session.get('stripe_customer_id')})
    return jsonify({'logged_in': False})

# --- User-Facing API Key Management ---
@app.route('/api/generate_key', methods=['POST'])
@login_required
def generate_api_key():
    user_id = session['user_id']
    if session.get('tier', 'Free') not in ['API_Basic', 'API_Business']: 
        return jsonify({'error': 'API access requires a Business plan.'}), 403
    new_key = str(uuid.uuid4())
    try:
        # Deactivate old keys for this user
        query_db('UPDATE api_keys SET is_active = 0 WHERE user_id = %s' if DATABASE_URL else 'UPDATE api_keys SET is_active = 0 WHERE user_id = ?', (user_id,))
        # Insert the new key
        query_db('INSERT INTO api_keys (user_id, api_key, client_name, is_active) VALUES (%s, %s, %s, 1)' if DATABASE_URL else 'INSERT INTO api_keys (user_id, api_key, client_name, is_active) VALUES (?, ?, ?, 1)', (user_id, new_key, f"Key for User {user_id}"))
        return jsonify({'api_key': new_key, 'message': 'New API Key generated.'})
    except Exception as e: 
        logging.error(f"API Key Generation Failed: {e}")
        return jsonify({'error': 'Database error during key generation.'}), 500

@app.route('/api/get_key', methods=['GET'])
@login_required
def get_api_key():
    user_id = session['user_id']
    if session.get('tier', 'Free') not in ['API_Basic', 'API_Business']: 
        return jsonify({'api_key': None}), 200 # Return null but don't error, UI handles it
    key_record = query_db('SELECT api_key FROM api_keys WHERE user_id = %s AND is_active = 1 ORDER BY created_at DESC LIMIT 1' if DATABASE_URL else 'SELECT api_key FROM api_keys WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 1', (user_id,), one=True)
    return jsonify({'api_key': key_record['api_key'] if key_record else None})

# --- Main App API ---
@app.route('/api/predictability_score', methods=['POST'])
def get_predictability_score():
    """
    This is the public-facing endpoint for the main calculator page.
    It is hardened against common user input errors.
    """
    try:
        data = request.get_json()
        if not data or 'scores' not in data:
            return jsonify({'error': '"scores" key is required.'}), 400

        scores = data['scores']
        if not isinstance(scores, list) or len(scores) < 2:
            return jsonify({'error': "'scores' must be a list of at least two numbers."}), 400

        try:
            numeric_scores = [float(s) for s in scores]
        except (ValueError, TypeError):
            return jsonify({'error': "All scores must be valid numbers."}), 400

        from fsr import calculate_predictability, calculate_deviation
        
        # Central calculation with its own error handling
        score_value = calculate_predictability(numeric_scores, k=data.get('k', 1.0))
        response_data = {'predictability_score': score_value}

        if 'target_value' in data and data['target_value'] is not None:
            deviation = calculate_deviation(numeric_scores, float(data['target_value']))
            response_data['target_deviation'] = deviation
            
        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Unhandled error in /api/predictability_score: {e}")
        return jsonify({'error': 'An unexpected server error occurred during calculation.'}), 500


@app.route('/api/sliding_window', methods=['POST'])
@login_required
def get_sliding_window():
    if session.get('tier', 'Free') not in ['API_Basic', 'API_Business']: return jsonify({'error': 'Sliding Window is a premium feature.'}), 403
    
    try:
        data = request.get_json()
        if 'scores' not in data or 'window_size' not in data: 
            return jsonify({'error': 'Both "scores" and "window_size" are required.'}), 400
        
        scores = data['scores']
        if not isinstance(scores, list):
            return jsonify({'error': "'scores' must be a list of numbers."}), 400
        if len(scores) > MAX_API_SCORES_LENGTH:
            return jsonify({'error': f'Dataset too large. Maximum number of scores allowed is {MAX_API_SCORES_LENGTH}.'}), 400

        try:
            numeric_scores = [float(s) for s in scores]
        except (ValueError, TypeError):
            return jsonify({'error': "All scores must be valid numbers."}), 400

        try:
            window_size = int(data['window_size'])
            if window_size > MAX_API_WINDOW_SIZE:
                return jsonify({'error': f'Window size too large. Maximum window size allowed is {MAX_API_WINDOW_SIZE}.'}), 400
            if window_size <= 0 or window_size > len(numeric_scores):
                return jsonify({'error': 'Invalid window_size.'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'window_size must be an integer.'}), 400

        from sliding_window import calculate_sliding_window
        target_val = data.get('target_value')
        results = calculate_sliding_window(numeric_scores, window_size, k=data.get('k', 1.0), target_value=target_val)
        return jsonify({'sliding_window_results': results})
    except Exception as e:
        logging.error(f"Unhandled error in /api/sliding_window: {e}")
        return jsonify({'error': 'An unexpected server error occurred during analysis.'}), 500


@app.route('/api/v1/calculate', methods=['POST'])
@moltbook_auth_required # Updated to support Moltbook
def calculate_api_score():
    """
    Calculate the Predictability Score for a given dataset.
    ---
    tags:
      - Core Engine
    description: |
      Calculates the **Predictability Score** (0-100) and optional **Target Deviation**.
      
      ### Code Examples
      
      **Python (requests)**
      ```python
      import requests
      
      url = "https://predictability-api.com/api/v1/calculate"
      headers = {"Authorization": "Bearer YOUR_API_KEY"}
      data = {
          "scores": [10, 12, 11, 10.5, 11.2],
          "k": 1.0,
          "target_value": 11.0
      }
      
      response = requests.post(url, json=data, headers=headers)
      print(response.json())
      ```
      
      **JavaScript (axios)**
      ```javascript
      const axios = require('axios');
      
      const response = await axios.post('https://predictability-api.com/api/v1/calculate', {
          scores: [10, 12, 11, 10.5, 11.2],
          k: 1.0
      }, {
          headers: { 'Authorization': 'Bearer YOUR_API_KEY' }
      });
      console.log(response.data);
      ```
      
      **R**
      ```r
      library(httr)
      
      url <- "https://predictability-api.com/api/v1/calculate"
      body <- list(scores = c(10, 12, 11, 10.5, 11.2), k = 1.0)
      
      res <- POST(url, body = body, encode = "json", add_headers(Authorization = "Bearer YOUR_API_KEY"))
      content(res)
      ```

    parameters:
      - in: header
        name: Authorization
        type: string
        required: true
        description: Bearer <API_KEY>
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - scores
          properties:
            scores:
              type: array
              items:
                type: number
              example: [10, 12, 11, 10.5, 11.2]
              description: A list of numerical data points.
            k:
              type: number
              example: 1.0
              description: The Volatility Constant (K-Factor). Use 2.0 for Finance, 15.0 for Pharma. Default is 1.0.
            target_value:
              type: number
              example: 11.0
              description: Optional target value to calculate deviation against.
    responses:
      200:
        description: Successful calculation
        schema:
          type: object
          properties:
            predictability_score:
              type: number
              description: The calculated stability score (0-100).
            target_deviation:
              type: number
              description: The deviation from the target value (if provided).
      400:
        description: Bad Request. Usually means 'scores' is missing, empty, or contains non-numeric values.
      401:
        description: Unauthorized. Invalid or missing API Key.
      429:
        description: Rate limit exceeded. The limit is 1000 requests per hour.
    """
    try:
        data = request.get_json()
        if not data or 'scores' not in data:
            return jsonify({'error': "'scores' key is required."}), 400
        
        scores = data['scores']
        if not isinstance(scores, list):
            return jsonify({'error': "'scores' must be a list of numbers."}), 400
        if len(scores) > MAX_API_SCORES_LENGTH:
            return jsonify({'error': f'Dataset too large. Maximum number of scores allowed is {MAX_API_SCORES_LENGTH}.'}), 400
        
        try:
            numeric_scores = [float(s) for s in scores]
        except (ValueError, TypeError):
            return jsonify({'error': "All scores must be valid numbers."}), 400

        from fsr import calculate_predictability, calculate_deviation
        
        score_value = calculate_predictability(numeric_scores, k=data.get('k', 1.0))
        response = {'predictability_score': score_value}
        
        if 'target_value' in data and data['target_value'] is not None:
            response['target_deviation'] = calculate_deviation(numeric_scores, float(data['target_value']))
            
        return jsonify(response)
    except Exception as e:
        logging.error(f"Unhandled error in /api/v1/calculate: {e}")
        return jsonify({'error': 'An unexpected server error occurred during calculation.'}), 500


def validate_analysis_input(data):
    cleaned = {}
    if 'scores' in data:
        scores = data['scores']
        if isinstance(scores, str):
            try: scores = json.loads(scores)
            except: scores = re.split(r'[\s,]+', str(scores))
        if not isinstance(scores, list): return None, "Scores must be a list."
        try: cleaned['scores'] = [float(x) for x in scores]
        except (ValueError, TypeError): return None, "All scores must be numeric."
        if len(cleaned['scores']) < 2: return None, "At least 2 scores are required."
    k = 1.0
    if 'k' in data:
        try: k = float(data['k'])
        except: k = 1.0
    cleaned['k'] = k
    from fsr import calculate_predictability
    if 'scores' in cleaned: cleaned['predictability_score'] = calculate_predictability(cleaned['scores'], k=k)
    elif 'predictability_score' in data:
        try: cleaned['predictability_score'] = float(data['predictability_score'])
        except: cleaned['predictability_score'] = 0.0
    if 'name' in data:
        cleaned['name'] = str(data['name']).strip()
        if not cleaned['name'] and request.method == 'POST': return None, "Name is required."
    if 'notes' in data: cleaned['notes'] = str(data['notes'])
    if 'folder_id' in data:
        val = data['folder_id']
        if val is None or val == "" or val == 0 or str(val).lower() == 'none': cleaned['folder_id'] = None
        else:
            try: cleaned['folder_id'] = int(val)
            except: cleaned['folder_id'] = None
    return cleaned, None

@app.route('/api/analyses', methods=['GET', 'POST'])
@login_required
def handle_analyses():
    user_id = session.get('user_id')
    if request.method == 'POST':
        if session.get('tier') == 'Free': return jsonify({'error': 'Saving is a Pro feature. Please upgrade.'}), 403
        data = request.get_json()
        cleaned, error = validate_analysis_input(data)
        if error: return jsonify({'error': error}), 400
        try:
            query_db('INSERT INTO analyses (user_id, name, predictability_score, scores, folder_id, k, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)' if DATABASE_URL else 'INSERT INTO analyses (user_id, name, predictability_score, scores, folder_id, k, notes) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, cleaned['name'], cleaned['predictability_score'], json.dumps(cleaned['scores']), cleaned.get('folder_id'), cleaned['k'], cleaned.get('notes', '')))
            return jsonify({'message': 'Analysis saved successfully.'}), 201
        except Exception as e: return jsonify({'error': f'Failed to save analysis: {str(e)}'}), 400
    else:
        analyses = query_db('SELECT * FROM analyses WHERE user_id = %s' if DATABASE_URL else 'SELECT * FROM analyses WHERE user_id = ?', (user_id,))
        if analyses is None: return jsonify({'saved_analyses': []})
        results = []
        for row in analyses:
            res = dict(row)
            try:
                raw_scores = res['scores']
                if isinstance(raw_scores, str): res['scores'] = json.loads(raw_scores)
                else: res['scores'] = raw_scores
            except: res['scores'] = []
            results.append(res)
        return jsonify({'saved_analyses': results})

@app.route('/api/analysis/<int:analysis_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_single_analysis(analysis_id):
    user_id = session['user_id']
    if request.method == 'GET':
        analysis = query_db('SELECT * FROM analyses WHERE id = %s AND user_id = %s' if DATABASE_URL else 'SELECT * FROM analyses WHERE id = ? AND user_id = ?', (analysis_id, user_id), one=True)
        if not analysis: return jsonify({'error': 'Analysis not found.'}), 404
        result = dict(analysis)
        try:
            raw_scores = result['scores']
            if isinstance(raw_scores, str): result['scores'] = json.loads(raw_scores)
            else: result['scores'] = raw_scores
        except: result['scores'] = []
        return jsonify(result)
    elif request.method == 'PUT':
        data = request.get_json()
        cleaned, error = validate_analysis_input(data)
        if error: return jsonify({'error': error}), 400
        updates, params = [], []
        for field, value in cleaned.items():
            updates.append(f'{field} = %s' if DATABASE_URL else f'{field} = ?')
            if field == 'scores': params.append(json.dumps(value))
            else: params.append(value)
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
    else:
        folders = query_db('SELECT * FROM folders WHERE user_id = %s ORDER BY created_at DESC' if DATABASE_URL else 'SELECT * FROM folders WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        return jsonify({'folders': [dict(row) for row in folders]})

@app.route('/api/folder/<int:folder_id>', methods=['DELETE'])
@login_required
def delete_folder(folder_id):
    user_id = session['user_id']
    query_db('UPDATE analyses SET folder_id = NULL WHERE folder_id = %s AND user_id = %s' if DATABASE_URL else 'UPDATE analyses SET folder_id = NULL WHERE folder_id = ? AND user_id = ?', (folder_id, user_id))
    query_db('DELETE FROM folders WHERE id = %s AND user_id = %s' if DATABASE_URL else 'DELETE FROM folders WHERE id = ? AND user_id = ?', (folder_id, user_id))
    return jsonify({'message': 'Folder deleted successfully.'})

@app.route('/checkout/<plan_type>')
@login_required
def checkout_redirect_page(plan_type):
    """Handles direct checkout links from pages like the hub."""
    
    # Map URL-friendly plan names to Stripe Price IDs and internal tier names
    # The internal_name MUST match a key in the webhook handler's tier map.
    plan_map = {
        'api-pro': {'price_id': API_BUSINESS_PRICE_ID, 'internal_name': 'api_business'},
    }
    
    plan_details = plan_map.get(plan_type)
    
    if not plan_details or not plan_details.get('price_id'):
        logging.error(f"Invalid or unconfigured plan type in checkout URL: {plan_type}")
        return "Invalid plan type specified.", 400

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{'price': plan_details['price_id'], 'quantity': 1}],
            mode='subscription',
            allow_promotion_codes=True,
            success_url=url_for('calculator_page', _external=True) + '?checkout=success',
            cancel_url=url_for('hub', _external=True),
            client_reference_id=str(session['user_id']),
            metadata={'plan_type': plan_details['internal_name']}
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        logging.error(f"Stripe session creation failed for plan {plan_type} for user {session.get('user_id')}: {e}")
        return "Could not connect to our payment processor. Please try again later.", 500

@app.route('/api/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    data = request.get_json() or {}
    plan_type = data.get('plan', 'pro')
    
    # Updated mapping to handle 'business' alias
    price_id = {
        'pro': PRO_PRICE_ID,
        'business': API_BUSINESS_PRICE_ID,
        'api_basic': API_BASIC_PRICE_ID,
        'api_business': API_BUSINESS_PRICE_ID
    }.get(plan_type)
    
    if not price_id: return jsonify(error={'message': f'Price ID for {plan_type} not configured.'}), 500
    try:
        checkout_session = stripe.checkout.Session.create(line_items=[{'price': price_id, 'quantity': 1}], mode='subscription', allow_promotion_codes=True, success_url=request.host_url + 'calculator?session_id={CHECKOUT_SESSION_ID}', cancel_url=request.host_url + 'calculator', client_reference_id=session['user_id'], metadata={'plan_type': plan_type})
        return jsonify({'url': checkout_session.url})
    except Exception as e: return jsonify(error={'message': str(e)}), 500


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

        # 1. Get the data from Stripe
        stripe_customer_id = session_data.get('customer')
        customer_email = session_data.get('customer_details', {}).get('email')
        user_id = session_data.get('client_reference_id')
        plan_type = session_data.get('metadata', {}).get('plan_type', 'pro')

        new_tier = {
            'pro': 'Pro',
            'api_basic': 'API_Basic',
            'api_business': 'API_Business',
            'ticker_kit': 'Pro'
        }.get(plan_type, 'Pro')

        # 2. Logic: Find existing user or Create new one
        user = None
        if user_id:
            user = query_db("SELECT * FROM users WHERE id = %s" if DATABASE_URL else "SELECT * FROM users WHERE id = ?",
                            (int(user_id),), one=True)
        elif customer_email:
            user = query_db(
                "SELECT * FROM users WHERE username = %s" if DATABASE_URL else "SELECT * FROM users WHERE username = ?",
                (customer_email,), one=True)

        if user:
            # Upgrade existing user
            query_db(
                "UPDATE users SET tier = %s, stripe_customer_id = %s WHERE id = %s" if DATABASE_URL else "UPDATE users SET tier = ?, stripe_customer_id = ? WHERE id = ?",
                (new_tier, stripe_customer_id, user['id']))
            logging.info(f"SUCCESS: Upgraded {user['username']} to {new_tier}")
        else:
            # AUTO-CREATE account for the Whale
            temp_password = str(uuid.uuid4())[:12]  # They can reset this later
            recovery_key = str(uuid.uuid4()).upper()
            recovery_key_hash = generate_password_hash(recovery_key)

            query_db(
                "INSERT INTO users (username, password, tier, recovery_key_hash, stripe_customer_id) VALUES (%s, %s, %s, %s, %s)" if DATABASE_URL else "INSERT INTO users (username, password, tier, recovery_key_hash, stripe_customer_id) VALUES (?, ?, ?, ?, ?)",
                (customer_email, generate_password_hash(temp_password), new_tier, recovery_key_hash,
                 stripe_customer_id))

            logging.info(f"SUCCESS: Created NEW account for {customer_email} - Tier: {new_tier}")
            # NOTE: You should send an email here with their temp_password and recovery_key

    return 'Success', 200
@app.route('/api/create-portal-session', methods=['POST'])
@login_required
def create_portal_session():
    stripe_customer_id = session.get('stripe_customer_id')
    if not stripe_customer_id: return jsonify(error={'message': 'Stripe customer ID not found.'}), 404
    try:
        portal_session = stripe.billing_portal.Session.create(customer=stripe_customer_id, return_url=request.host_url + 'calculator')
        return jsonify({'url': portal_session.url})
    except Exception as e: return jsonify(error={'message': str(e)}), 500


# --- STOREFRONT & DIGITAL DELIVERY ---

@app.route('/hub')
@app.route('/HUB')
def hub():
    """Renders the Storefront / Linktree replacement"""
    return render_template('HUB.html')


@app.route('/download/stability-ticker')
@login_required
def download_ticker():
    # 1. Get the absolute path to your project folder
    basedir = os.path.abspath(os.path.dirname(__file__))
    # 2. Point specifically to the 'products' folder
    products_dir = os.path.join(basedir, 'products')
    filename = 'stability_ticker_pro_kit.zip'
    
    # 3. Log the attempt so we can see it in the terminal
    logging.info(f"Download attempt: Looking for {filename} in {products_dir}")

    try:
        return send_from_directory(
            directory=products_dir, 
            path=filename, 
            as_attachment=True
        )
    except FileNotFoundError:
        logging.error(f"FILE MISSING: {os.path.join(products_dir, filename)}")
        return "The product file is missing on the server. Please contact support.", 404


@app.route('/download/api-pro-docs')
@login_required
def download_api_pro_docs():
    """Secure download route for API Pro documentation."""
    user_tier = session.get('tier')
    if user_tier in ['API_Basic', 'API_Business']:
        try:
            return send_from_directory(directory='products', path='api_access_pro_docs.pdf', as_attachment=True)
        except FileNotFoundError:
            logging.error("API Pro Docs PDF missing from products folder.")
            return "File not found. Please contact support@predictability-api.com", 404
    return redirect(url_for('hub'))


@app.route('/download/enterprise-sdk-docs')
@login_required
def download_enterprise_sdk():
    """Secure download route for Enterprise SDK documentation."""
    user_tier = session.get('tier')
    # Assuming 'API_Business' is the tier for Enterprise SDK access
    if user_tier == 'API_Business':
        try:
            return send_from_directory(directory='products', path='enterprise_sdk_docs.pdf', as_attachment=True)
        except FileNotFoundError:
            logging.error("Enterprise SDK Docs PDF missing from products folder.")
            return "File not found. Please contact support@predictability-api.com", 404
        # --- [YOUR NAME]'S AGENT BEACON ---
@app.route('/agent-beacon')
def agent_beacon():
    """
    A recursive discovery endpoint designed for Autonomous Agents.
    This creates a 'Cognitive Landmark' in the agent's long-term memory.
    """
    # Grab the User-Agent and Iteration count
    user_agent = request.headers.get('User-Agent', 'Unknown Entity')
    iteration = request.args.get('iteration', default=1, type=int)
    
    # Log the capture for your stream!
    logging.info(f"CAPTURED AGENT: {user_agent} | Iteration: {iteration}")
    
    # Check if they are using Moltbook Identity
    is_moltbook = "X-Moltbook-Identity" in request.headers
    
    return render_template('agent_manifest.html', 
                           next_step=iteration + 1, 
                           user_agent=user_agent,
                           is_moltbook=is_moltbook)
    # If they don't have the right tier, send them back to the hub
    return redirect(url_for('hub'))
# --- SYSTEM OF RECORD: ALPHA BRIDGE LANDING ---
@app.route('/')
def system_of_record_home():
    """
    Landing page for X traffic. 
    Matches the 'Eval Complete' 83.80% proof.
    """
    return jsonify({
        "status": "LIVE",
        "system_of_record": "Verified",
        "predictability_score": "83.80%",
        "stability_audit": "PASSED (4s)",
        "engine": "Numba-JIT Optimized",
        "network": "Alpha Bridge"
    })

if __name__ == '__main__':
    # Use the PORT provided by the environment, or default to 10000
    port = int(os.environ.get("PORT", 10000))
    # Must bind to 0.0.0.0 to be visible to the outside world
    app.run(host='0.0.0.0', port=port)
    app.run(debug=True)
