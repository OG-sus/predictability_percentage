# Predictability Score API Documentation

Welcome to the Predictability Score API. This API allows you to calculate the consistency of any dataset using our proprietary algorithm.

## Base URL
`https://www.predictability-api.com`

## Authentication
All API requests must include your API Key in the `Authorization` header.

`Authorization: Bearer YOUR_API_KEY`

---

## Endpoints

### 1. Calculate Standard Score
Calculates a single predictability score for a list of numbers.

*   **URL:** `/api/v1/calculate`
*   **Method:** `POST`
*   **Content-Type:** `application/json`

**Request Body:**
```json
{
  "scores": [10, 12, 10, 12, 10, 12],
  "k": 1.0
}
```
*   `scores` (Required): A list of at least two numbers.
*   `k` (Optional): The volatility constant. Default is 1.0. (0.5 = Sports, 2.0 = Finance, 15.0 = Pharma).

**Success Response (200 OK):**
```json
{
  "predictability_score": 91.5405312186223
}
```

---

### 2. Calculate Sliding Window (Premium)
Performs a rolling analysis to detect drift and stability over time. Ideal for Quality Control (QC) and trend analysis.

*   **URL:** `/api/v1/sliding_window`
*   **Method:** `POST`
*   **Content-Type:** `application/json`

**Request Body:**
```json
{
  "scores": [10, 12, 10, 12, 10, 12, 15, 20],
  "window_size": 3,
  "k": 1.0
}
```
*   `scores` (Required): A list of data points (e.g., pill weights, stock prices).
*   `window_size` (Required): The number of data points in each calculation window.
*   `k` (Optional): The volatility constant.

**Success Response (200 OK):**
```json
{
  "sliding_window_results": [
    {
      "index": 0,
      "window_start": 1,
      "window_end": 3,
      "score": 91.54
    },
    {
      "index": 1,
      "window_start": 2,
      "window_end": 4,
      "score": 88.21
    }
    // ... more windows
  ]
}
```

---

## Error Codes
*   **400 Bad Request:** Missing data or invalid format.
*   **401 Unauthorized:** Invalid or missing API Key.
*   **403 Forbidden:** Your plan does not support this feature.
*   **500 Internal Server Error:** Something went wrong on our end.
