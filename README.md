# Gemini Computer Use Web Agent Demo

This repository contains a Python script (`web_agent.py`) demonstrating a powerful, multi-turn web automation agent powered by the **Gemini Computer Use** tool. The agent uses Playwright to programmatically control a web browser, analyzing the visual layout on every turn and taking natural browser actions (typing, clicking, navigating) to complete complex user goals.

---

## 🏎️ Mercedes-Benz Portal Demo Overview

This version is specifically configured to test and verify complex multi-turn workflows against a high-fidelity local replica of the **Mercedes-Benz Talent Acquisition Portal** (`index.html`). 

### What the Application Does
1. **Dynamic Local Server**: Launches a lightweight, background HTTP server serving the luxury-themed recruitment portal locally.
2. **Interactive Sign-In**: The agent automatically identifies suggested login credentials, inputs the recruiter email and password, and authenticates.
3. **Report Generation & Download**:
   - Accepts specific starting and ending dates in natural language.
   - Operates the UI to input those dates cleanly.
   - Clicks the `"Generate & Download CSV"` button.
4. **Intercepts & Saves Downloads**: Includes a native Playwright download listener that captures client-side files compiled by the app and saves them directly into the current directory.

---

## 🛠️ Requirements & Prerequisites

Ensure the following are installed and configured on your machine:

1. **Python 3.9+** (and standard virtual environment utilities).
2. **Google Cloud SDK (`gcloud` CLI)**.
3. **Application Default Credentials (ADC)** set up on your machine:
   ```bash
   gcloud auth application-default login
   ```
4. **Active Google Cloud Project ID** with Vertex AI enabled.

---

## 🚀 Setup & Execution Instructions

Follow these steps to set up and execute the agent locally:

### 1. Initialize Virtual Environment & Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

### 2. Configure Environment Variables
Set your Google Cloud Project ID and location:
```bash
export GOOGLE_CLOUD_PROJECT="[your-project-id]"
export GOOGLE_LOCATION="global"
export MODEL_ID="gemini-2.5-computer-use-preview-10-2025"
export USE_MERCEDES_PORTAL="true"
```

### 3. Run the Agent

#### Option A: Headless Mode (Standard Verification)
Runs the entire flow in the background (headless browser) and automatically intercept-saves the generated CSV to the local directory:
```bash
export HEADLESS="true"
python web_agent.py "Open a new browser tab and navigate to http://127.0.0.1:8000. Type 'recruiter@mercedes-benz.com' in the email box, type 'PremiumCareer2026' in the password box, and click Authenticate. Once the export page loads, select '2026-07-01' as the starting date, '2026-07-15' as the ending date, and click Generate & Download CSV."
```

#### Option B: Visible Mode (Interactive Demo)
Launches a visible Chromium window on your screen so you can watch the agent work in real-time.

> [!IMPORTANT]
> **macOS Screen Recording Permissions Required for Option B**:
> - If prompted by macOS when the browser opens, navigate to **System Settings > Privacy & Security > Screen Recording** and check the box to allow your terminal/IDE.
> - **You must completely quit (`Cmd + Q`) and restart your terminal/editor** after granting this permission. Otherwise, the agent will receive blank screenshots and fail to execute actions.

```bash
export HEADLESS="false"
python web_agent.py "Open a new browser tab and navigate to http://127.0.0.1:8000. Type 'recruiter@mercedes-benz.com' in the email box, type 'PremiumCareer2026' in the password box, and click Authenticate. Once the export page loads, select '2026-07-01' as the starting date, '2026-07-15' as the ending date, and click Generate & Download CSV."
```

*Note: When executing the click action to download the CSV, the console will prompt you to confirm the action. Press `y` and `Enter` in the terminal to continue.*

---

## 🔍 Root Cause Analysis & Technical Fixes

Before these updates, the agent was experiencing failures during multi-turn automation. The following sections outline the specific diagnostic findings and resolutions implemented:

### 1. The Multi-Turn Vision Bug ("Working Blind")
* **The Symptom**: The agent could successfully complete the first action (such as opening the browser or navigating), but on subsequent turns, it either clicked wildly on incorrect elements or stalled, reporting that it *"did not have the screenshot yet"*.
* **The Root Cause**: In Gemini's multi-turn Computer-Use vision API, subsequent screenshots returned to the model must be in standard **PNG** format, nested inside the `FunctionResponse` object's inner `parts` list with `mime_type="image/png"`. 
  The original script captured subsequent screenshots as `image/jpeg` and nested them as jpeg. The Vertex AI backend visual adapter silently discarded these JPEG frames, leaving the model blind on all subsequent turns.
* **The Fix**: Refactored the screenshot capture logic inside `web_agent.py` to capture screenshots exclusively using standard PNG format and pack them with the correct `"image/png"` mime-type inside the nested `FunctionResponse` parts.

### 2. Schema Violation Mismatches (`400 INVALID_ARGUMENT`)
* **The Symptom**: Attempts to send screenshots on multi-turn interactions resulted in a `400 INVALID_ARGUMENT` API exception from the Gemini server.
* **The Root Cause**: When compiling a `user` content response following a model's `function_call`, Gemini's schema rules prohibit mixing `FunctionResponse` parts with sibling `inline_data` parts within the same `Content.parts` list.
* **The Fix**: Removed sibling parts from the `user` turn message and packed the PNG screenshot strictly inside the `FunctionResponse.parts` list. This adheres perfectly to the Computer-Use API types, resolving all schema exceptions.

### 3. Date Input Selector Optimization
* **The Symptom**: Attempting to click date numerals inside standard browser/OS date-picker calendar dropdowns often failed or closed the popover window without applying the change, due to date-picker rendering quirks in headless browser layouts.
* **The Fix**: The input elements in `index.html` were optimized to accept standard keyboard values cleanly. The agent successfully learned to directly type standard dates (e.g. typing `07/01/2026` and `07/15/2026` into the starting and ending date input boxes), guaranteeing 100% reliable execution.
