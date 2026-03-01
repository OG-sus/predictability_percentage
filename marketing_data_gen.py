import yfinance as yf
import pandas as pd

def get_marketing_data(ticker, period="2d", interval="1h"):
    """
    Fetches market data. 
    Default is the most recent 24 hours of hourly data.
    """
    print(f"\n--- Fetching Data for {ticker} (Period: {period}, Interval: {interval}) ---")
    try:
        # Download data
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        
        if data.empty:
            print("Error: No data found. Check the ticker symbol.")
            return

        # Extract 'Close' prices robustly
        if isinstance(data.columns, pd.MultiIndex):
            # Handles cases where yfinance returns a multi-level column index,
            # which can happen even with a single ticker.
            # We select the 'Close' column for the requested ticker.
            close_prices = data['Close'][ticker]
        else:
            # Handles the standard case where 'Close' is a top-level column.
            close_prices = data['Close']

        # Drop NaNs
        close_prices = close_prices.dropna()

        # If using the default hourly fetch, ensure we only get the last 24 hours
        if period == "2d" and interval == "1h":
            close_prices = close_prices.tail(24)

        # Convert to list of rounded floats
        prices_list = [round(x, 2) for x in close_prices.tolist()]

        # Format as comma-separated string
        output_string = ", ".join(map(str, prices_list))

        print(f"\nSuccessfully fetched {len(prices_list)} data points.")
        print("\n--- COPY THE DATA BELOW FOR YOUR DASHBOARD ---\n")
        print(output_string)
        print("\n----------------------------------------------\n")
        
        # Calculate a suggested target for the dashboard
        if prices_list:
            avg_price = sum(prices_list) / len(prices_list)
            print(f"Suggested Target (Average): {round(avg_price, 2)}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("Marketing Data Generator for Predictability API")
    print("Examples: SPY, QQQ, BTC-USD, NVDA")
    
    while True:
        ticker = input("\nEnter Ticker Symbol (or 'q' to quit): ").strip().upper()
        if ticker == 'Q':
            break
        
        # Ask user if they want to use the default (24h hourly)
        use_defaults_input = input("Use default (last 24h hourly)? (y/n): ").lower()
        
        if use_defaults_input == 'n':
            period_input = input("Enter period (e.g., 3mo, 5d, 1y): ").strip()
            interval_input = input("Enter interval (e.g., 1d, 1wk, 1mo): ").strip()
            # Call the function with the user's custom parameters
            get_marketing_data(ticker, period=period_input, interval=interval_input)
        else:
            # Call the function with the default parameters
            get_marketing_data(ticker)
