# 📡 Stability Ticker™ Pro Kit
**A "Predictability-API" Stability Module**

The Stability Ticker is a lightweight, high-performance OBS widget that turns any Google Sheet into a professional broadcast-grade ticker. 

### 🚀 Quick Start
1. **Prepare your Data:** Open the `smart_ticker_template.csv` and import it into a Google Sheet.
2. **Publish to Web:** In Google Sheets, go to `File > Share > Publish to Web`. Select `Comma-separated values (.csv)`.
3. **Generate your Look:** Open `ticker_generator.html` in your browser. 
4. **Paste your ID:** Put your Google Sheet ID into the generator and customize your colors/fonts.
5. **Add to OBS:** Copy the generated link. In OBS, add a **Browser Source**, check **Local File**, and point it to `ticker_render.html`. Paste your parameters into the URL field.

### 🛡️ Stability Features
* **Logic Guard:** Only rows marked `TRUE` in the `Is_Live` column will appear.
* **Connection Guard:** Real-time status alerts if your internet or sheet connection blips.
* **Ultra-Low Overhead:** Designed to run smoothly even on 16GB RAM setups during heavy streaming.

---
© 2026 Predictability-API. Build for Stability.