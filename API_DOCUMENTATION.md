# Predictability Score™ API Documentation

Welcome to the Predictability Score™ API. This institutional-grade engine allows you to quantify the consistency and reliability of any dataset using our proprietary Volatility Constant (k) algorithm.

## Base URL
`https://www.predictability-api.com`

## Authentication
All API requests must include your API Key in the `Authorization` header. You can find your API key in the **Developer Settings** section of your dashboard.

`Authorization: Bearer YOUR_API_KEY`

---

## Endpoints

### 1. Calculate Standard Score
Calculates a single predictability score (0-100%) for a given dataset.

*   **URL:** `/api/v1/calculate`
*   **Method:** `POST`
*   **Content-Type:** `application/json`

**Request Body:**
```json
{
  "scores": [10.5, 12.1, 10.8, 11.9, 10.2],
  "k": 1.0,
  "target_value": 11.0
}
```
*   `scores` (Required): A list of at least two numbers.
*   `k` (Optional): The Volatility Constant. Default is 1.0. (0.5 = Sports, 2.0 = Finance, 15.0 = Pharma).
*   `target_value` (Optional): If provided, the engine also returns the percentage deviation from this target.

**Success Response (200 OK):**
```json
{
  "predictability_score": 91.54,
  "target_deviation": 0.90
}
```

---

### 2. Calculate Sliding Window (Institutional/Enterprise)
Performs a temporal stability analysis to detect "Data Drift." Ideal for real-time Quality Control (QC) and identifying the exact moment a system becomes unstable.

*   **URL:** `/api/v1/sliding_window`
*   **Method:** `POST`
*   **Content-Type:** `application/json`

**Request Body:**
```json
{
  "scores": [100, 102, 101, 99, 100, 105, 110, 108],
  "window_size": 5,
  "k": 15.0
}
```
*   `scores` (Required): A list of data points (e.g., pill weights, sensor readings).
*   `window_size` (Required): The number of data points per rolling calculation.
*   `k` (Optional): The Volatility Constant.

**Success Response (200 OK):**
```json
{
  "sliding_window_results": [
    {
      "index": 0,
      "window_start": 1,
      "window_end": 5,
      "score": 98.21
    },
    {
      "index": 1,
      "window_start": 2,
      "window_end": 6,
      "score": 85.45
    }
  ]
}
```

---

## Service Tiers
*   **API Basic:** $200/mo - Access to `/api/v1/calculate` with high rate limits.
*   **API Business:** $500/mo - Access to all endpoints plus priority support.
*   **API Institutional:** $2,000+/mo - Custom K-Factor consultation and infinite temporal analysis via Sliding Window.

## Error Codes
*   **400 Bad Request:** Missing data, invalid format, or less than 2 data points.
*   **401 Unauthorized:** Invalid or missing API Key.
*   **403 Forbidden:** Feature not included in your current tier.
*   **500 Internal Server Error:** Unexpected engine failure.
