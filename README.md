# 🏎️ Gemini Computer Use ADK Agent (Mercedes-Benz Talent Acquisition Portal)

This repository showcases how to implement and run a **Custom Agent** using Google's **Agent Development Kit (ADK)** and its official, interactive **ADK Developer Playground Web UI**. 

Instead of a standalone custom-built web application, this repo demonstrates how developers can leverage the rich, native ADK ecosystem to easily test, debug, and run **Gemini 2.5 Computer Use** with full, live browser automation streams directly in their web browser.

---

## 🌟 What This Repository Showcases

This agent is configured to automate complex, multi-turn recruitment and data extraction workflows against a high-fidelity local replica of the **Mercedes-Benz Talent Acquisition Portal** (`index.html`).

### 1. The Power of Google's Agent Development Kit (ADK)
* **Interactive Developer UI**: Spins up a local playground server allowing you to chat with your agent, trigger tasks, and watch the agent's browser window execute actions (clicks, keyboard input, navigations) in a live side-by-side split screen.
* **Declarative Agent Orchestration**: Uses ADK’s modular `Agent`, `App`, and `ComputerUseToolset` classes for cleaner, enterprise-grade architecture.

### 2. Standard Enterprise-Grade Optimizations
* **Automatic Context Caching (Cost & Latency Reduction)**: Uses ADK's native `ContextCacheConfig` to cache repetitive session histories (such as previous screenshots and instructions) on Google's servers. This slashes multi-turn input token costs by **75% to 90%** and decreases model response times.
* **Structured Cost Tracker & Auditor**: Automatically calculates the actual USD cost of each turn based on standard Gemini 2.5 Pro pricing ($1.25/1M input, $10.00/1M output). It logs this structured data locally to `app/session_costs.csv` (perfect for spreadsheet audits) and `app/session_costs.log`, and prints live summaries to the terminal console!
* **Dynamic Multi-Backend Selection**: Gracefully checks for a local `GEMINI_API_KEY`. If present, it routes requests through the lightning-fast **Google AI Studio (Gemini Developer API)**. If absent, it securely defaults to Vertex AI using standard `gcloud` Application Default Credentials (ADC).
* **Conversational Short-Circuiting**: Subclasses Gemini with a custom greeting interceptor. Simple pleasantries (like *"hello"* or *"hi"*) are responded to instantly in text without starting the browser or spending expensive visual tokens!

---

## 🛠️ Requirements & Prerequisites

Ensure you have the following installed on your machine:

1. **Python 3.10+** (and standard virtual environment utilities).
2. **Google Cloud SDK (`gcloud` CLI)** — *required if using Vertex AI backend.*
3. **Application Default Credentials (ADC)** — *required if using Vertex AI backend:*
   ```bash
   gcloud auth application-default login
   ```
4. **Google AI Studio API Key** (Recommended for local developer speeds and free-tier optimization):
   ```bash
   export GEMINI_API_KEY="AIzaSy..."
   ```

---

## 🚀 Setup & Execution Instructions

### 1. Initialize Virtual Environment & Install Dependencies
First, create your environment and install the required packages:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Launch the Interactive ADK Playground
To launch the agent inside the rich ADK Developer Playground Web UI, run:

```bash
UV_DEFAULT_INDEX="https://pypi.org/simple" agents-cli playground
```

Once executed, your console will print:
```text
Starting your agent playground...
Will be available at: http://127.0.0.1:8080/dev-ui/?app=app
```

### 3. Run the Automation
1. Open the URL `http://127.0.0.1:8080/dev-ui/?app=app` in your browser.
2. In the chat interface, click **New Session** at the top right to clear any active history.
3. Submit a goal to the agent, such as:
   > *"Open the browser, log into the portal at http://127.0.0.1:8000 using recruiter@mercedes-benz.com / PremiumCareer2026, and export talent data for July 1st through July 15th."*
4. **Watch the live stream**: The Web UI will show you exactly what the agent is seeing, where its virtual cursor is clicking, and what actions it takes in real-time!

---

## 📊 cost & Action Auditing (Data Analysis)

Every single browser interaction (click, text typing, scroll) is recorded locally for cost analysis. 

* **Live Terminal Logs**: See cost breakdowns in your terminal as they happen:
  ```text
  💵 [COST TRACKER] Call used 14,842 tokens (14,410 input, 432 output). Estimated Cost: $0.022332 USD
  ```
* **Structured Audit Table (`app/session_costs.csv`)**: Compatible with Excel and Pandas, recording:
  * `timestamp`: Date & Time of action.
  * `action`: The exact action taken (e.g., `click_at(x=480, y=587)`).
  * `prompt_tokens`: Input tokens.
  * `candidates_tokens`: Output tokens.
  * `total_cost_usd`: Total USD cost of that action.
* **Readable Action Log (`app/session_costs.log`)**: Plain-text transaction records.

*(Note: `app/session_costs.csv` and `app/session_costs.log` are added to `.gitignore` by default to avoid cluttering your repository with session records).*

---

## 📂 Project Architecture

* `app/agent.py`: The core ADK agent definition. Houses our custom `NonStreamingGemini` subclass which intercepts greetings, applies fail-fast retry configurations, runs context caching, and manages token pricing calculations.
* `app/playwright.py`: Configures the browser, default portal environment flags (`USE_MERCEDES_PORTAL=True`), and viewport resolutions.
* `index.html`: High-fidelity local Mercedes-Benz Talent Acquisition Portal used for browser automation target testing.
* `pyproject.toml` & `uv.lock`: Modern python packaging configurations.
