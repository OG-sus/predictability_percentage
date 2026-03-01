import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

# --- CONFIGURATION (Adjust these as you grow) ---
PRICE_PRO = 19.99
PRICE_BUSINESS = 129.99
SERVER_COST_ESTIMATE = 7.00  # Render Hobby Plan approx
STRIPE_FEE_PERCENT = 0.029   # 2.9%
STRIPE_FEE_FIXED = 0.30      # +30 cents
TAX_RATE = 0.30              # 30% for Uncle Sam

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
        return sqlite3.connect(db_path)

def calculate_business_health():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Get User Counts
        cursor.execute("SELECT tier, COUNT(*) FROM users GROUP BY tier")
        rows = cursor.fetchall()
        
        counts = {'Free': 0, 'Pro': 0, 'API_Basic': 0, 'API_Business': 0, 'Enterprise': 0}
        for row in rows:
            # Handle different DB return formats (tuple vs dict)
            tier = row[0] if isinstance(row, tuple) else row['tier']
            count = row[1] if isinstance(row, tuple) else row['count']
            
            # Normalize tier names
            if tier in counts:
                counts[tier] = count
            elif tier == 'Business': # Handle legacy name if any
                counts['API_Business'] += count

        # 2. Calculate Revenue (Gross MRR)
        revenue_pro = counts['Pro'] * PRICE_PRO
        revenue_biz = (counts['API_Basic'] + counts['API_Business']) * PRICE_BUSINESS
        gross_mrr = revenue_pro + revenue_biz

        # 3. Calculate Expenses (Stripe Fees)
        # Fee = (Revenue * 2.9%) + (30 cents * Number of Transactions)
        total_transactions = counts['Pro'] + counts['API_Basic'] + counts['API_Business']
        stripe_fees = (gross_mrr * STRIPE_FEE_PERCENT) + (total_transactions * STRIPE_FEE_FIXED)
        
        # 4. Net Revenue (Before Tax)
        net_revenue = gross_mrr - stripe_fees - SERVER_COST_ESTIMATE

        # 5. The Tax Man (30%)
        tax_reserve = net_revenue * TAX_RATE if net_revenue > 0 else 0
        
        # 6. True Pocket Money
        take_home = net_revenue - tax_reserve

        # --- DISPLAY ---
        print("\n" + "="*40)
        print("   🚀 FOUNDER MODE: BUSINESS SNAPSHOT")
        print("="*40)
        
        print(f"\n👥  USERS")
        print(f"    Free Users:      {counts['Free']}")
        print(f"    Pro (${PRICE_PRO}):     {counts['Pro']}")
        print(f"    Biz (${PRICE_BUSINESS}):    {counts['API_Basic'] + counts['API_Business']}")
        print(f"    Total Customers: {sum(counts.values())}")

        print(f"\n💰  REVENUE (MRR)")
        print(f"    Gross MRR:       ${gross_mrr:,.2f}")
        print(f"    - Stripe Fees:   ${stripe_fees:,.2f}")
        print(f"    - Server Costs:  ${SERVER_COST_ESTIMATE:,.2f}")
        print("-" * 30)
        print(f"    Net Operating:   ${net_revenue:,.2f}")

        print(f"\n🏛️  TAXES (The 30% Rule)")
        print(f"    Set Aside NOW:   ${tax_reserve:,.2f}")

        print(f"\n💵  TRUE PROFIT")
        print(f"    Your Pocket:     ${take_home:,.2f}")
        print("="*40 + "\n")

        if take_home < 0:
            print("⚠️  STATUS: Burn Phase (Investing in Growth)")
        elif take_home < 1000:
            print("🌱  STATUS: Ramen Profitable (Keep Pushing)")
        else:
            print("🚀  STATUS: Scaling (Time to Incorporate?)")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    calculate_business_health()
