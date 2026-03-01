import time
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fsr import calculate_predictability
import torch
from transformers import pipeline, set_seed

# --- CONFIGURATION ---
SHEET_ID = "1F3V-nmqchQE2-pauoRCVWDdZKLUIOLbSt1qeXvcUz6o"
SHEET_TAB_NAME = "Sheet1"
CREDENTIALS_FILE = "service_account.json"
AI_SCORE_CELL = "M2"
AI_STATUS_CELL = "N2"
DATA_STREAM_CELL = "P2"

# --- AI SETUP ---
print("Loading AI model (DistilGPT-2). This may take a moment on first run...")
try:
    # Using a text-generation pipeline is easiest
    generator = pipeline('text-generation', model='distilgpt2')
    set_seed(random.randint(0, 10000)) # Add some randomness
    print("✅ AI Model loaded successfully.")
except Exception as e:
    print(f"🚨 Could not load AI model. Do you have torch and transformers installed? (pip install torch transformers). Error: {e}")
    generator = None # Set generator to None if it fails

def connect_to_sheet():
    """Connects to Google Sheets using the service account."""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    try:
        worksheet = sheet.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.sheet1
    return worksheet

def get_ai_prediction(sequence):
    """Asks the real AI to predict the next number in a sequence."""
    if not generator:
        print("AI model not available. Simulating...")
        return sequence[-1] + random.uniform(-2, 2) # Fallback to simulation

    prompt = f"The following is a sequence of market prices: {', '.join(map(str, sequence))}. The next price is "
    
    try:
        # Generate text and parse the first number found
        outputs = generator(prompt, max_length=len(prompt.split()) + 5, num_return_sequences=1)
        generated_text = outputs[0]['generated_text']
        
        # Find the first number after the prompt
        prediction_part = generated_text[len(prompt):]
        
        # A simple way to find a number in the generated text
        found_numbers = [float(s) for s in prediction_part.split() if s.replace('.', '', 1).isdigit()]
        
        if found_numbers:
            print(f"🤖 AI Predicted: {found_numbers[0]}")
            return found_numbers[0]
        else:
            print("⚠️ AI did not return a valid number. Simulating a small change.")
            return sequence[-1] + random.uniform(-1, 1)

    except Exception as e:
        print(f"🚨 AI generation failed: {e}. Simulating.")
        return sequence[-1] + random.uniform(-2, 2)

def main():
    print("--- REAL AI Audit Stream Started ---")
    print(f"Writing to {SHEET_TAB_NAME} cells {AI_SCORE_CELL}, {AI_STATUS_CELL}, & {DATA_STREAM_CELL}")
    print("Press Ctrl+C to stop.")
    
    # Initial data buffer (using floats for consistency)
    data_stream = [round(100.0 + random.uniform(-2, 2), 2) for _ in range(10)]
    
    while True:
        try:
            # Re-connect inside the loop to handle timeouts/disconnects gracefully
            worksheet = connect_to_sheet()

            # 1. Get new prediction from the REAL AI
            new_value = get_ai_prediction(data_stream)
            data_stream.append(round(new_value, 2))
            data_stream.pop(0)
            
            # 2. Calculate Score
            # Changed k from 1.0 to 0.5 to calibrate for AI noise
            score = calculate_predictability(data_stream, k=0.5)
            
            # 3. Determine Status
            if score >= 80:
                status = "✅ STABLE"
            elif score >= 50:
                status = "⚠️ DRIFTING"
            else:
                status = "🚨 HALLUCINATING"
            
            # 4. Update Google Sheet
            recent_data_str = "[" + ", ".join([str(x) for x in data_stream[-5:]]) + "]"
            
            worksheet.update_acell(AI_SCORE_CELL, f"{score:.2f}")
            worksheet.update_acell(AI_STATUS_CELL, status)
            worksheet.update_acell(DATA_STREAM_CELL, recent_data_str)
            
            print(f"Updated Sheet: Score={score:.2f} | Status={status} | Data={recent_data_str}")
            
            # 5. Wait
            time.sleep(10)
            
        except Exception as e:
            print(f"An error occurred in the main loop: {e}")
            print("Reconnecting in 15 seconds...")
            time.sleep(15)

if __name__ == "__main__":
    main()
