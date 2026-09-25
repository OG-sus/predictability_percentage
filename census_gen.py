import os
import pandas as pd
import requests
from dotenv import load_dotenv

# 1. Load the secret API key from .env file
load_dotenv()
CENSUS_KEY = os.getenv("CENSUS_API_KEY")

if not CENSUS_KEY:
    raise ValueError("API Key missing! Check your .env file.")

BASE_URL = "https://api.census.gov/data/timeseries/eits/mrts"


def fetch_census_series():
    print("Fetching Economic Indicators time series from Census Bureau...")

    all_records = []

    # Loop through years from 2000 to present to gather full time-series
    for year in range(2000, 2027):
        params = {
            "get": "cell_value,time_slot_id",
            "category_code": "44000",  # Total Retail and Food Services
            "data_type_code": "SM",  # Sales - Monthly
            "seasonally_adj": "YES",  # Seasonally Adjusted
            "for": "us:1",
            "time": str(year),  # Queries full 12 months for each year
            "key": CENSUS_KEY,
        }

        response = requests.get(BASE_URL, params=params)

        if response.status_code == 200:
            data = response.json()
            # Skip the header row (data[0]) and store rows
            all_records.extend(data[1:])
        elif response.status_code == 204:
            # Skip years where data isn't published yet
            continue
        else:
            print(
                f"Error fetching year {year}: {response.status_code} - {response.text}"
            )

    if not all_records:
        print("No data retrieved.")
        return None

    # Convert aggregated data to Pandas DataFrame
    headers = ["cell_value", "time_slot_id", "us", "time"]
    df = pd.DataFrame(all_records, columns=headers)

    # Clean and structure for FSR / Predictability-API
    df["value"] = pd.to_numeric(df["cell_value"], errors="coerce")
    df = df.dropna(subset=["value"])

    # Convert time_slot_id (e.g. 2024-01) to datetime
    df["date"] = pd.to_datetime(df["time_slot_id"], format="%Y-%m")
    df = df.sort_values("date").reset_index(drop=True)

    clean_df = df[["date", "value"]]

    print(
        f"\nSuccessfully fetched {len(clean_df)} months of data ({clean_df['date'].min().strftime('%Y-%m')} to {clean_df['date'].max().strftime('%Y-%m')})."
    )
    return clean_df


if __name__ == "__main__":
    df = fetch_census_series()
    if df is not None:
        print("\n--- Cleaned Data Sample for Predictability-API ---")
        print(df.tail(12))