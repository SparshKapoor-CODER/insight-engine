# Insight Engine 🔍

An automated data storytelling engine. Upload a raw CSV or Excel file and get a fully generated PDF report with charts, insights, and business narration — no analyst needed.

---

## What it does

1. You upload a `.csv` or `.xlsx` file (up to 10,000 rows)
2. It profiles the dataset using pandas
3. Sends the profile to an LLM (Groq / LLaMA) which decides what charts to plot
4. Python generates the charts using matplotlib + seaborn
5. Each chart's data is sent back to the LLM for business narration
6. A clean PDF report is assembled and ready to download

---

## Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Backend    | Python, Flask                     |
| Data       | Pandas, NumPy                     |
| Charts     | Matplotlib, Seaborn               |
| LLM        | Groq API (LLaMA 3.3 70B)          |
| PDF        | ReportLab                         |
| Frontend   | HTML, CSS, Vanilla JS             |

---

## Project Structure

```
insight-engine/
│
├── main.py                  # Entry point, starts Flask server
├── config.py                # Loads env variables, defines paths
├── .env                     # API keys (never commit this)
├── requirements.txt
│
├── /api
│   └── routes.py            # POST /upload and GET /report/<id>
│
├── /core
│   ├── profiler.py          # Pandas profiling → profile dict
│   ├── llm_analyst.py       # Sends profile to LLM → chart plan JSON
│   ├── chart_engine.py      # Executes chart plan → PNG files
│   ├── narrator.py          # Sends chart data to LLM → insight text
│   └── report_builder.py    # Assembles PDF from charts + narrations
│
├── /utils
│   ├── file_handler.py      # Validates and reads CSV/XLSX into DataFrame
│   └── data_cleaner.py      # Cleans nulls, fixes dtypes, parses dates
│
├── /storage
│   ├── /uploads             # Temporary uploaded files
│   ├── /charts              # Generated PNG charts
│   └── /reports             # Final PDF reports
│
└── /frontend
    ├── index.html           # Dropzone UI
    └── style.css
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourname/insight-engine.git
cd insight-engine
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your `.env` file

```
GROQ_API_KEY=your-groq-api-key-here
MODEL_NAME=llama-3.3-70b-versatile
MAX_ROWS=10000
MAX_CHARTS=6
```

Get your free Groq API key at [console.groq.com](https://console.groq.com)

### 4. Run the server

```bash
python main.py
```

### 5. Open in browser

```
http://127.0.0.1:5000
```

Upload your file and hit **Generate Report**.

---

## How the LLM pipeline works

```
Raw file
  → Pandas profiling → column names + dtypes + stats (text)
      → LLM Call 1 → JSON chart plan (what to plot, which columns, aggregation)
          → Python executes → aggregated data tables (text)
              → LLM Call 2 per chart → business narration (text)
                  → PDF assembler → charts (PNG) + narration → final report
```

The LLM never sees the raw data or the chart images. It only sees:
- A structured profile summary (Call 1)
- Small aggregated data tables per chart (Call 2)

This keeps token usage minimal and costs low.

---

## Supported Chart Types

| Type        | Use case                              |
|-------------|---------------------------------------|
| `bar`       | Categorical comparisons               |
| `line`      | Trends over time                      |
| `scatter`   | Correlation between two numerics      |
| `histogram` | Distribution of a single column       |
| `pie`       | Proportions (max 6 categories)        |
| `box`       | Spread and outliers                   |

---

## Limitations

- Maximum 10,000 rows per file
- Works best with clean, structured tabular data
- Groq free tier has token rate limits — large datasets may slow down narration
- No authentication or multi-user support (single user local tool for now)

---

## Roadmap

- [ ] Support for more file types (JSON, Google Sheets)
- [ ] User can select which charts to include
- [ ] Multiple report themes / PDF styles
- [ ] Deploy to cloud (Railway / Render)
- [ ] Add authentication for multi-user SaaS

---

## Contributors

Thanks to all the amazing people who contributed to this project ❤️

<a href="https://github.com/SparshKapoor-CODER/insight-engine/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SparshKapoor-CODER/insight-engine&max=500&columns=20" />
</a>

---

## License

MIT License. Free to use, modify, and distribute.
