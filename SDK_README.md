# Predictability Score™ SDK (Enterprise Edition)

> **"Don't just call an API. Integrate a Logic Guard."**

The **Predictability Score SDK** is an institutional-grade analytics engine that quantifies the stability of any time-series dataset. It allows you to embed our proprietary **Euler-decay math** and **K-Factor tuning** directly into your own infrastructure—secure, offline, and with zero latency.

---

## 🚀 Why use the SDK?

*   **Zero Latency:** Runs locally on your servers using Numba-optimized JIT compilation.
*   **100% Privacy:** Your data never leaves your firewall. No API calls. No external logging.
*   **AI Guardrails:** Audit the output stability of your LLM agents or autonomous systems in real-time.
*   **Industrial Grade:** Tuned for high-frequency trading, manufacturing sensors, and health monitoring.

---

## 📦 Installation

You can install the SDK directly from the provided wheel file:

```bash
pip install predictability_score-1.0.0-py3-none-any.whl
```

*Requirements: Python 3.8+, NumPy, Numba*

---

## ⚡ Quickstart

### 1. The Basic Audit
Check the stability of a dataset in 3 lines of code.

```python
from fsr import calculate_predictability

# Your data (e.g., sensor readings, stock prices, agent confidence scores)
data = [10, 12, 11, 10.5, 11.2, 10.8]

# Calculate Score (0-100%)
# k=1.0 is Standard. Use k=2.0 for Finance, k=15.0 for Pharma.
score = calculate_predictability(data, k=1.0)

print(f"Stability Score: {score:.2f}%")
# Output: Stability Score: 93.73%
```

### 2. The Sliding Window (Temporal Drift)
Detect *when* a system started to fail.

```python
from sliding_window import calculate_sliding_window

# A stream of data that becomes unstable at the end
stream = [10, 10, 10, 10, 12, 15, 20, 50, 100]

# Scan with a window size of 3
results = calculate_sliding_window(stream, window_size=3, k=2.0)

for window in results:
    print(f"Time: {window['window_end']}, Score: {window['score']:.1f}%")
```

---

## 🔧 Configuration: The K-Factor™

The `k` parameter is your sensitivity knob.

| K-Factor | Sensitivity | Use Case |
| :--- | :--- | :--- |
| **0.5** | Low | **Sports Analytics:** Forgiving of occasional "off nights." |
| **1.0** | Medium | **General Purpose:** Server load, traffic analysis. |
| **2.0** | High | **FinTech:** Strict punishment for volatility. |
| **15.0** | Critical | **Pharma / AI Safety:** Zero-tolerance for hallucination or drift. |

---

## 🛡️ AI Safety & Hallucination Guardrails

Use the SDK to verify the consistency of your AI agents.

```python
# Example: Monitoring an LLM's confidence scores over 5 responses
agent_confidence = [0.99, 0.98, 0.99, 0.45, 0.99]

score = calculate_predictability(agent_confidence, k=15.0)

if score < 80:
    print("🚨 ALERT: Agent is hallucinating or unstable. Halting execution.")
else:
    print("✅ Agent is stable.")
```

---

## 📜 License

This software is proprietary and confidential.
Unauthorized copying, distribution, or reverse engineering of this file, via any medium, is strictly prohibited.
**Copyright © 2026 Predictability API.**
