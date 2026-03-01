# Predictability API - Quick Start Guide

## 1. Get Your API Key
1. Log in to [predictability-api.com/calculator](https://predictability-api.com/calculator).
2. Click **"Get API Key"** in the dashboard.
3. Copy the key (starts with `Bearer ...` or just the UUID).

## 2. Install Dependencies
We use standard JSON requests. No special SDK is required, but we provide a helper script.

```bash
pip install requests
```

## 3. Make Your First Call
Use the included `api_client.py` or curl:

```bash
curl -X POST https://predictability-api.com/api/v1/calculate \
     -H "Authorization: Bearer YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '{"scores": [10, 12, 11, 10.5, 11.2], "k": 1.0}'
```

## 4. Interpreting the Score
- **90-100:** Rock Solid. Process is highly predictable.
- **70-89:** Normal Variance. Standard operating conditions.
- **40-69:** Drift Detected. The process is becoming erratic.
- **0-39:** Critical Instability. Immediate intervention required.

## 5. Support
Need help tuning the `k-factor` for your specific data?
Email us at: support@predictability-api.com
