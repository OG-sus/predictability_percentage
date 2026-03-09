# Copilot Instructions

## What This Project Is

**Predictability Score™ (FSR – Financial Stability Ratio)** is a SaaS analytics engine that quantifies dataset stability as a single 0–100% score. The core algorithm uses a modified Coefficient of Variation (CV) combined with an exponential decay function: `Score = 100 * e^(-k * |CV|)`. The **K-Factor™** is a tunable sensitivity knob (0.5 = sports/forgiving, 2.0 = finance/strict, 15.0 = pharma/zero-tolerance).

The app is deployed on Render as a Flask/Gunicorn service backed by PostgreSQL in production and SQLite locally.

## Commands

```bash
# Run the API server (port 10000)
python api.py

# Run the Streamlit monitoring dashboard
streamlit run dashboard.py

# Run all tests
python tests.py

# Run a single test
python -m unittest tests.TestPredictabilityMath.test_perfect_consistency

# Initialize the database
python init_db.py

# Install dependencies
pip install -r requirements.txt

# Build & migrate (used by Render on deploy)
./build.sh
```

## Architecture

- **`api.py`** — The Flask application (1150+ lines). All routes, auth middleware, Stripe payment webhooks, REST API endpoints, and session management live here. This is the main server entry point.
- **`fsr.py`** — The core mathematical engine. Contains Numba JIT-compiled functions (`@jit(nopython=True)`) for C-speed calculation. `api.py` imports from here.
- **`predictability_score/`** — A separately distributable Python package wrapping `fsr.py` logic. `core.py` has the algorithm; `window.py` has sliding window logic. Published via `setup.py`.
- **`sliding_window.py`** — Temporal drift detection; feeds the `/api/v1/sliding_window` endpoint.
- **`dashboard.py`** — Streamlit real-time monitor that polls `http://localhost:10000` every second.
- **`templates/`** — Jinja2 HTML templates. **`static/`** — CSS, JS, images.
- **`schema.sql`** — Authoritative DB schema. `init_db.py` loads it. `migrate_*.py` scripts are one-off migration runners.

## Database

Two environments, one codebase — queries are written to handle both:

```python
# Always branch on DATABASE_URL for placeholder syntax
query_db(
    'SELECT * FROM table WHERE id = %s' if DATABASE_URL else 'SELECT * FROM table WHERE id = ?',
    (id,),
    one=True  # True → returns single dict; False → list of dicts
)
```

- **Production**: PostgreSQL via `DATABASE_URL` env var
- **Development**: SQLite (`database.db`)
- **Migrations**: Flask-Migrate (`flask db migrate` / `flask db upgrade`). One-off migration scripts are in `migrate_*.py`.

## Auth & Tiers

Two auth systems coexist in `api.py`:

1. **Session auth** (`@login_required` decorator) — Checks `session["user_id"]`. Password hashing via `werkzeug.security`.
2. **API key auth** (`@api_key_required` decorator) — `Authorization: Bearer <key>` header. Keys stored in `api_keys` table. Rate-limited to 1000 req/hour per key.
3. **Moltbook agent auth** — `X-Moltbook-Identity` header verified against `moltbook.com`; falls back to API key if absent.

User tiers: `Free` → `Pro` → `API_Basic` → `API_Business`. Stripe manages upgrades; `update_user_tier.py` can manually set tiers.

## Key Conventions

**Route pattern** — All routes follow this structure:
```python
@app.route('/path', methods=['POST'])
@login_required  # or @api_key_required
def handler():
    data = request.get_json()
    # ...
    return jsonify({'result': value}), 200
```

**Error responses** — Always `jsonify({'error': 'message'})` with an appropriate HTTP status code. Database errors get a rollback before the response.

**Input validation** — Use `validate_analysis_input()` to clean/coerce score arrays. It handles JSON strings, comma-separated values, and mixed types. Never trust raw input shapes.

**Numba functions** — The `_calculate_predictability_numba()` and `_calculate_deviation_numba()` functions are JIT-compiled and must receive `np.array(..., dtype=np.float64)`. Public wrapper functions handle the conversion.

**Logging** — `logging.basicConfig(level=logging.INFO)`. Log errors with `logging.error(f"Error: {e}")`. The app logs per-request IP, method, path, and user agent.

**Stripe** — Webhook at `/api/webhook` verifies signature with `stripe.Webhook.construct_event()`. Checkout sessions created at `/api/create-checkout-session`. Never hardcode price IDs — they come from env vars.

## External Services

| Service | Purpose | Key env var |
|---|---|---|
| Stripe | Payments & subscriptions | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| PostgreSQL (Render) | Production database | `DATABASE_URL` |
| Moltbook | AI agent identity verification | (header-based, no key needed) |
| NBA Stats API | Data generation scripts only | (no auth required) |

## Tests

Tests are in `tests.py` using Python's built-in `unittest`. The test class is `TestPredictabilityMath`. Tests exercise the math directly — no HTTP/database mocking required for the core logic tests. There is no pytest config; use `unittest` directly.


## Specialized Agents
Refer to the /agents directory for specific personas:
- tech_specialist.md: Use for SDK integration and technical docs.
- sales_qualifier.md: Use for business logic and lead conversion.
