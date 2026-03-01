import requests
import json

class PredictabilityClient:
    """
    Official Python Client for the Predictability API.
    https://predictability-api.com
    """
    
    def __init__(self, api_key):
        """
        Initialize the client with your API Key.
        Get a key at: https://predictability-api.com/calculator
        """
        self.api_key = api_key
        self.base_url = "https://predictability-api.com/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def calculate(self, scores, k=1.0, target_value=None):
        """
        Calculate the Predictability Score for a list of numbers.
        
        :param scores: List of floats/ints (e.g., [10, 12, 11])
        :param k: Sensitivity factor (default 1.0)
        :param target_value: Optional target to calculate deviation against
        :return: Dictionary containing the score and deviation
        """
        payload = {
            "scores": scores,
            "k": k
        }
        if target_value is not None:
            payload["target_value"] = target_value

        response = requests.post(f"{self.base_url}/calculate", json=payload, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API Error {response.status_code}: {response.text}")

    def sliding_window(self, scores, window_size, k=1.0):
        """
        Perform a Sliding Window analysis to detect drift over time.
        
        :param scores: List of floats/ints
        :param window_size: Size of the moving window (e.g., 10)
        :param k: Sensitivity factor (default 1.0)
        :return: List of window results
        """
        payload = {
            "scores": scores,
            "window_size": window_size,
            "k": k
        }

        response = requests.post(f"{self.base_url}/sliding_window", json=payload, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API Error {response.status_code}: {response.text}")

# --- Example Usage ---
if __name__ == "__main__":
    # 1. Initialize
    # Replace with your actual API Key
    client = PredictabilityClient(api_key="YOUR_API_KEY_HERE")

    # 2. Data
    my_data = [10, 12, 11, 10.5, 11.2, 10.8, 12.1, 11.5, 15.0, 18.0]

    try:
        # 3. Calculate Score
        result = client.calculate(my_data, k=1.0)
        print(f"Predictability Score: {result['predictability_score']}")

        # 4. Detect Drift
        windows = client.sliding_window(my_data, window_size=5)
        print(f"Sliding Window Results: {json.dumps(windows, indent=2)}")
        
    except Exception as e:
        print(f"Error: {e}")
