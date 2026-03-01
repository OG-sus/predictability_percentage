# 📘 The Stability Ticker - Product Bible

## 🚀 The Vision
**"The Lego of Stream Data."**
Don't just add a ticker. Build a **Modular Data Dashboard**.
Stop cluttering your screen with one giant, boring bar. Use **Stability Modules** to create stackable, customizable data feeds that fit your unique layout.

## ⚡ Marketing Hooks & Lingo
*   **"Stability Modules":** The individual ticker widgets (Pills, Bars, Boxes).
*   **"Logic Guard":** The underlying technology that ensures data integrity.
*   **"No-Code Broadcast Suite":** Turning a simple Google Sheet into a professional TV-style feed.
*   **"Fontophile's Dream":** Massive library of curated fonts to match any brand.
*   **"Live Textures":** Custom background images for premium branding.

---

## 🛠️ The Product: "Stability Ticker"

### Core Features
1.  **Smart Template:** A pre-built Google Sheet that handles the logic.
2.  **Visualizer Engine:** Automatically converts data into visual cues (Trend Arrows ⬆️⬇️).
3.  **Stackable Design:** Generate unlimited unique URLs for different parts of the screen.
4.  **Live Customizer:** Real-time preview of fonts, colors, dimensions, and textures.

### The "Presets" (Planned)
*   **Classic News Bar:** 100% Width, 60px Height. The standard bottom-screen crawl.
*   **Corner Pill:** 30% Width, 80px Height, Rounded Corners. Perfect for crypto/stock prices in a corner.
*   **Header Strip:** 100% Width, 40px Height. Thin, unobtrusive top bar for announcements.
*   **Spotlight Box:** 20% Width, 150px Height. A focused square for "Current Song" or "Top Donor."

---

## 📖 User Manual: The "Key" to the Smart Sheet

### 1. The Columns
Your Google Sheet must have specific headers for the ticker to read it correctly.

| Column Header | Description | Example |
| :--- | :--- | :--- |
| **Symbol** | The main label or name of the item. | `BTC`, `LeBron`, `Goal` |
| **Price** | The primary value to display. | `$98,500`, `25 pts`, `$500/1000` |
| **Change** | (Optional) Secondary info, usually a percentage or difference. | `+2.5%`, `+5`, `(Live)` |
| **Trend** | Controls the arrow icon. | `UP` (⬆️), `DOWN` (⬇️), `FLAT` (no icon) |
| **Is_Live** | **The Master Switch.** Only rows marked `TRUE` will appear on stream. | `TRUE`, `FALSE` |

### 2. How to Use
1.  **Copy the Template:** Use our provided `smart_ticker_template.csv`.
2.  **Connect Data:** Use Google Sheet formulas (like `=GOOGLEFINANCE`) to auto-populate the `Price` and `Change` columns.
3.  **Go Live:** Type `TRUE` in the `Is_Live` column for any row you want to show.
4.  **Hide:** Type `FALSE` to instantly remove it from the stream without deleting the data.

### 3. Advanced Tips
*   **Formulas are your friend:** You don't have to type data manually. Link cells to other sheets or APIs.
*   **Batch Control:** You can use a checkbox in your sheet to toggle `TRUE`/`FALSE` for multiple rows at once.

---

## 🗺️ Roadmap
*   **Phase 1 (Current):** Horizontal scrolling, custom fonts/colors/dimensions, Google Sheet integration.
*   **Phase 2:** Vertical scrolling (news list style), "Sparkline" mini-charts.
*   **Phase 3:** The SDK (`npm install stability-ticker`) for developers.
