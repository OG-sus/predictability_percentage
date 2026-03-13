import time
import random
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fsr import calculate_predictability

# ---------------------------------------------------------------------------
# CONFIGURATION — edit these to point at the right sheet / tab / row
# ---------------------------------------------------------------------------
SHEET_ID          = "1F3V-nmqchQE2-pauoRCVWDdZKLUIOLbSt1qeXvcUz6o"
SHEET_TAB_NAME    = "Sheet1"   # change to "CBB", "MLB", "Finance", "Golf", etc.
CREDENTIALS_FILE  = "service_account.json"

# Cells the auditor writes to (for the row being audited)
AI_SCORE_CELL     = "M2"
AI_STATUS_CELL    = "N2"
DATA_STREAM_CELL  = "P2"

# How many data points to keep in the rolling audit window
WINDOW_SIZE       = 10

# Seconds between audit cycles
POLL_INTERVAL     = 10

# K-factor: 0.5 = forgiving (good for noisy AI outputs), 1.0 = standard
K_FACTOR          = 0.5

# Column index (0-based) in the sheet that holds the live data string (Column K = index 10)
# The auditor pulls this as the "truth" sequence the AI must reason about.
REAL_DATA_COL_IDX = 10

# ---------------------------------------------------------------------------
# AI MODEL SETUP
# ---------------------------------------------------------------------------
print("Loading AI model (DistilGPT-2)…")
try:
    from transformers import pipeline, set_seed
    generator = pipeline('text-generation', model='distilgpt2')
    set_seed(random.randint(0, 9999))
    print("✅ AI model loaded.")
except Exception as e:
    print(f"⚠️  Could not load AI model ({e}). Running in simulation mode.")
    generator = None


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def connect_to_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        return sheet.sheet1


def extract_number(text: str, fallback: float) -> float:
    """
    Pull the first valid number out of any generated text string.
    Uses regex so it handles decimals, negatives, and comma-formatted numbers.
    """
    cleaned = text.replace(',', '')
    matches = re.findall(r'-?\d+(?:\.\d+)?', cleaned)
    if matches:
        return float(matches[0])
    return fallback


def get_live_sequence(worksheet) -> list[float] | None:
    """
    Read the current live data string from the sheet (Column K of the live row).
    Returns a list of floats, or None if the data is unavailable.
    """
    try:
        rows = worksheet.get_all_values()
        for row in rows[1:]:  # skip header
            if len(row) > 4 and str(row[4]).strip().upper() == 'TRUE':
                raw = row[REAL_DATA_COL_IDX] if len(row) > REAL_DATA_COL_IDX else ''
                if raw:
                    numbers = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', raw)]
                    if len(numbers) >= 3:
                        return numbers
        return None
    except Exception:
        return None


def get_ai_prediction(sequence: list[float]) -> float:
    """
    Present the AI with a numeric sequence and ask it to identify the next value.
    The prompt is domain-neutral — no market/gambling framing.
    """
    if not generator:
        # Simulation: mean-revert with small noise
        mean = sum(sequence) / len(sequence)
        return round(mean + random.uniform(-abs(mean) * 0.03, abs(mean) * 0.03), 2)

    context = ', '.join(f'{v:.2f}' for v in sequence[-9:])
    prompt = (
        f"Analyze this data sequence: {context}. "
        f"Based on the pattern, the next value in the sequence is "
    )

    try:
        outputs = generator(
            prompt,
            max_new_tokens=10,
            num_return_sequences=1,
            pad_token_id=50256,
        )
        generated = outputs[0]['generated_text']
        new_text = generated[len(prompt):]
        prediction = extract_number(new_text, fallback=sequence[-1])
        print(f"   🤖  AI read: \"{new_text.strip()[:40]}\" → parsed {prediction:.2f}")
        return round(prediction, 2)
    except Exception as e:
        print(f"   ⚠️  Generation error ({e}), using simulation.")
        mean = sum(sequence) / len(sequence)
        return round(mean + random.uniform(-abs(mean) * 0.03, abs(mean) * 0.03), 2)


def audit_status(score: float, accuracy_pct: float | None) -> str:
    """
    Return a clean, domain-neutral status label.
    Optionally factors in prediction accuracy when real data is available.
    """
    if score >= 80:
        label = "✅ CONSISTENT"
    elif score >= 55:
        label = "⚠️  VARIABLE"
    else:
        label = "🚨 UNSTABLE"

    if accuracy_pct is not None:
        label += f"  |  {accuracy_pct:.1f}% accuracy"

    return label


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------

def main():
    print("=" * 55)
    print("  FSR AI Auditor  —  Consistency Monitor")
    print(f"  Tab: {SHEET_TAB_NAME}  |  Window: {WINDOW_SIZE}  |  k={K_FACTOR}")
    print("=" * 55)
    print("Press Ctrl+C to stop.\n")

    # Seed the prediction window — will be replaced by live sheet data if available
    prediction_log: list[float] = []
    cycle = 0

    while True:
        try:
            worksheet = connect_to_sheet()
            cycle += 1
            print(f"— Cycle {cycle} —")

            # Pull the current live sequence from the sheet (optional ground truth)
            live_sequence = get_live_sequence(worksheet)

            if live_sequence:
                # Use the last 9 live values as context; AI predicts the 10th
                context = live_sequence[-9:]
                actual  = live_sequence[-1]  # the real current value
                prediction = get_ai_prediction(context[:-1])  # hide the last point from AI

                # Accuracy: how close was the AI to the real value?
                if actual != 0:
                    accuracy = max(0.0, 100.0 - abs((prediction - actual) / actual) * 100)
                else:
                    accuracy = None

                print(f"   📊  Actual: {actual:.2f}  |  AI Predicted: {prediction:.2f}"
                      + (f"  |  Accuracy: {accuracy:.1f}%" if accuracy is not None else ""))
            else:
                # No live sheet data — run the AI on its own generated sequence
                if not prediction_log:
                    prediction_log = [round(50.0 + random.uniform(-5, 5), 2) for _ in range(9)]
                prediction = get_ai_prediction(prediction_log)
                accuracy = None

            # Append prediction to the rolling audit window
            prediction_log.append(prediction)
            if len(prediction_log) > WINDOW_SIZE:
                prediction_log.pop(0)

            # Score the AI's own output consistency
            score = calculate_predictability(prediction_log, k=K_FACTOR) if len(prediction_log) >= 3 else 0.0
            status = audit_status(score, accuracy if live_sequence else None)

            # Write to sheet
            recent_str = '[' + ', '.join(f'{v:.2f}' for v in prediction_log[-5:]) + ']'
            worksheet.update_acell(AI_SCORE_CELL, f'{score:.2f}')
            worksheet.update_acell(AI_STATUS_CELL, status)
            worksheet.update_acell(DATA_STREAM_CELL, recent_str)

            print(f"   📝  Score: {score:.2f}%  |  Status: {status}")
            print(f"   💾  Written → {AI_SCORE_CELL}, {AI_STATUS_CELL}, {DATA_STREAM_CELL}\n")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nAudit stopped.")
            break
        except Exception as e:
            print(f"Error in audit loop: {e}\nRetrying in 15 s…")
            time.sleep(15)


if __name__ == "__main__":
    main()

