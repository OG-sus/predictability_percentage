import requests
import json

class PredictabilityClient:
    """
    Official Python Client for the Predictability Score API.
    """
    def __init__(self, api_key, base_url="https://predictability-api.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def calculate_score(self, data_points, k_factor=1.0):
        """
        Calculates the stability score for a list of numbers.
        :param data_points: List[float] - The time-series data.
        :param k_factor: float - Sensitivity (Default 1.0). Use 2.0 for Finance.
        :return: dict - The API response.
        """
        endpoint = f"{self.base_url}/api/v1/calculate"
        payload = {
            "scores": data_points,
            "k": k_factor
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return None

    def detect_drift(self, data_points, window_size=10, k_factor=1.0):
        """
        Runs a Sliding Window analysis to find WHEN the data became unstable.
        :param window_size: int - How many points to analyze at a time.
        """
        endpoint = f"{self.base_url}/api/v1/sliding_window"
        payload = {
            "scores": data_points,
            "window_size": window_size,
            "k": k_factor
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return None

# --- Usage Example ---
if __name__ == "__main__":
    # 1. Initialize
    API_KEY = "YOUR_API_KEY_HERE"
    client = PredictabilityClient(API_KEY)

    # 2. Fake Data (Stable then Unstable)
    sensor_data = [10, 10.1, 9.9, 10.0, 10.2, 15.0, 8.0, 12.0, 14.0, 6.0]

    # 3. Get Score
    print("Calculating Score...")
    result = client.calculate_score(sensor_data)
    print(f"Overall Stability: {result}")

    # 4. Detect Drift
    print("\nChecking for Drift...")
    drift = client.detect_drift(sensor_data, window_size=3)
    if drift:
        for window in drift['sliding_window_results']:
            print(f"Window {window['window_index']}: Score {window['score']}")
