# Insight Engine — Product Roadmap
### From Local Prototype to Deployable SaaS

**Current State:** Working local prototype, 5.5/10 architecture score  
**Target State:** Deployed, sellable SaaS product  
**Builder:** Sparsh — B.Tech CSE (AI/ML), VIT Bhopal  

---

## Overview

```
Phase 0  →  Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5
Cleanup     Harden      Deploy      Product     Monetize    Scale
(Now)       (2 weeks)   (1 week)    (1 month)   (2 weeks)   (ongoing)
```

---

## Phase 0 — Critical Fixes Before Anything Else
**Timeline: This week | Effort: ~2 days**

These are the issues the architect flagged as HIGH severity.
Do not move to Phase 1 until all of these are done.

### 0.1 — Groq API Retry Logic
**File:** `core/llm_analyst.py`, `core/narrator.py`  
**Why:** Single transient rate limit error kills the entire report with no recovery.

```python
pip install tenacity
```

Wrap every Groq call:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _call_groq(prompt):
    ...
```

### 0.2 — Parallel Narrator Calls
**File:** `core/narrator.py`  
**Why:** 6 sequential API calls = ~18s wait. Parallel = ~4s.

```python
from concurrent.futures import ThreadPoolExecutor

def narrate(chart_results, log=None):
    with ThreadPoolExecutor(max_workers=4) as ex:
        insights = list(ex.map(_get_insight, chart_results))
    return [{"chart_id": c["chart_id"], "insight_text": i}
            for c, i in zip(chart_results, insights)]
```

### 0.3 — LLM Response Validator
**File:** `core/llm_analyst.py`  
**Why:** LLM returning a non-existent column name causes silent KeyError crash.

After `json.loads(raw)`, add:
```python
def _validate_plan(plan, df_columns):
    for chart in plan["charts"]:
        assert chart["x_column"] in df_columns, f"Invalid column: {chart['x_column']}"
        if chart.get("y_column"):
            assert chart["y_column"] in df_columns, f"Invalid column: {chart['y_column']}"
        assert chart["chart_type"] in ["bar","line","scatter","histogram","pie","box"]
        assert chart["aggregation"] in ["sum","mean","count","max","min","none"]
    return plan
```

### 0.4 — File Magic Byte Validation
**File:** `utils/file_handler.py`  
**Why:** Extension spoofing lets anyone upload arbitrary files.

```python
MAGIC_BYTES = {
    ".xlsx": b"PK\x03\x04",   # ZIP format
    ".csv":  None              # No magic bytes, validated by pandas
}

def _validate_magic(filepath, ext):
    if MAGIC_BYTES.get(ext):
        with open(filepath, "rb") as f:
            header = f.read(4)
        if header != MAGIC_BYTES[ext]:
            raise ValueError("File content does not match declared extension.")
```

### 0.5 — Storage Cleanup After Report Build
**File:** `api/routes.py`  
**Why:** Uploads and chart PNGs accumulate forever, disk fills silently.

After successful PDF build in routes.py:
```python
import glob

# Delete uploaded file
os.remove(filepath)

# Delete chart PNGs for this report
for png in glob.glob(os.path.join(CHARTS_PATH, f"{report_id}_*.png")):
    os.remove(png)
```

---

## Phase 1 — Harden the Backend
**Timeline: 2 weeks | Effort: Medium**

Make the codebase production-ready before touching deployment.

### 1.1 — Replace Flask Dev Server with Gunicorn
```bash
pip install gunicorn
```

Replace `main.py`:
```python
# main.py — dev only
if __name__ == "__main__":
    app.run(debug=False, port=5000)
```

Add `Procfile` for production:
```
web: gunicorn main:app --workers 2 --timeout 120 --bind 0.0.0.0:$PORT
```

### 1.2 — Add a Job Queue (Celery + Redis)
**Why:** Right now the HTTP request hangs open for 30-60 seconds while the pipeline runs.
The correct pattern is: accept the upload → return a job ID immediately → process async → poll for status.

```
pip install celery redis
```

New flow:
```
POST /upload → returns { job_id: "abc123" } immediately (< 1 second)
     ↓
Celery worker runs pipeline in background
     ↓
GET /status/{job_id} → { status: "processing" | "done" | "failed" }
     ↓
GET /report/{job_id} → serves PDF when done
```

Frontend polls `/status/{job_id}` every 3 seconds and shows a progress indicator.

### 1.3 — Input Validation & Rate Limiting
```bash
pip install flask-limiter
```

```python
from flask_limiter import Limiter

limiter = Limiter(app, default_limits=["10 per hour"])

@router.route("/upload", methods=["POST"])
@limiter.limit("5 per hour")
def upload():
    ...
```

Also add:
- Max file size cap: `app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB`
- Filename sanitization: `from werkzeug.utils import secure_filename`

### 1.4 — Structured Error Responses
Replace bare `500` responses with typed error objects:
```python
return jsonify({
    "error": True,
    "code": "LLM_PARSE_FAILURE",
    "message": "Could not parse LLM response. Please try again.",
    "report_id": report_id
}), 500
```

Frontend can show specific messages instead of generic "Something went wrong".

### 1.5 — Write Smoke Tests
```bash
pip install pytest
```

Minimum three tests:
```
tests/
  test_profiler.py      # profiler returns expected keys
  test_llm_validator.py # rejects bad column names
  test_pipeline.py      # full pipeline on 10-row CSV produces a PDF
```

Run with `pytest tests/` before every deployment.

### 1.6 — Environment Separation
Add `config.py` environment awareness:
```python
ENV = os.getenv("ENV", "development")
DEBUG = ENV == "development"
```

Separate `.env.development` and `.env.production` files.
Never run `debug=True` in production.

---

## Phase 2 — Deploy to Cloud
**Timeline: 1 week | Effort: Low-Medium**

Get it running on a real URL.

### 2.1 — Choose Your Deployment Platform

For a student/early product, **Railway** is the best choice:
- Free tier available
- Auto-deploys from GitHub push
- Built-in Redis (for Celery)
- No DevOps knowledge needed
- Scales to paid when you need it

Alternatives:
| Platform | Best for | Cost |
|----------|---------|------|
| Railway | Easiest, full stack | Free → $5/mo |
| Render | Simple Flask apps | Free → $7/mo |
| Fly.io | More control | Free → usage-based |
| AWS EC2 | Full control, production | $10-30/mo |

### 2.2 — Migrate Storage to Cloud Object Storage
Local filesystem doesn't work on cloud platforms (ephemeral containers).

Replace `/storage/` with **Cloudflare R2** (free tier, S3-compatible):
```bash
pip install boto3
```

```python
import boto3

s3 = boto3.client("s3",
    endpoint_url=os.getenv("R2_ENDPOINT"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("R2_SECRET_KEY"),
)

# Upload PDF
s3.upload_file(local_path, "insight-engine", f"reports/{report_id}.pdf")

# Generate download URL (expires in 1 hour)
url = s3.generate_presigned_url("get_object",
    Params={"Bucket": "insight-engine", "Key": f"reports/{report_id}.pdf"},
    ExpiresIn=3600
)
```

Free tier: 10GB storage, 1M requests/month. More than enough.

### 2.3 — Add a Minimal Database
You need to track job status, user uploads, and later — user accounts.

Use **PostgreSQL on Railway** (included free):
```bash
pip install psycopg2-binary sqlalchemy
```

Start with one table:
```sql
CREATE TABLE reports (
    id          VARCHAR(8) PRIMARY KEY,
    status      VARCHAR(20) DEFAULT 'pending',
    filename    VARCHAR(255),
    pdf_url     TEXT,
    error_msg   TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### 2.4 — Set Up CI/CD
Connect GitHub repo to Railway.
Every push to `main` auto-deploys.
Add a GitHub Action that runs `pytest tests/` before deploy — never ship broken code.

```yaml
# .github/workflows/test.yml
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install -r requirements.txt
      - run: pytest tests/
```

### 2.5 — Custom Domain
Buy `insightengine.in` or `cocoainsights.io` on Namecheap (~₹800/year).
Connect to Railway in 5 minutes via CNAME record.

---

## Phase 3 — Build the Product
**Timeline: 1 month | Effort: High**

Turn the tool into something people actually want to use and pay for.

### 3.1 — User Authentication
```bash
pip install flask-login bcrypt
```

Add a `users` table. Simple email + password to start.
Later: Google OAuth via `flask-dance` (one weekend of work).

Every report tied to a user. Users can only see their own reports.

### 3.2 — Report History Dashboard
Replace the single-page upload with a proper dashboard:
```
/dashboard   → list of past reports with status, filename, date
/upload      → upload new file
/report/{id} → view/download specific report
```

Use **Jinja2 templates** (already in Flask) to render server-side HTML.
Or build a React frontend if you're comfortable — connect via REST API.

### 3.3 — Redesign the Frontend Properly
Current frontend is functional but bare. For a sellable product it needs:
- Landing page explaining what the product does
- Pricing page
- Dashboard (report history)
- Upload flow with real progress bar (WebSocket or SSE)
- Report viewer (render PDF in-browser, not just download)

Use **Tailwind CSS** — fast to write, looks professional.

### 3.4 — Report Customization
Let users control the output before generation:
- Choose which charts to include/exclude
- Set report title and company name
- Choose color theme (light/dark/brand colors)
- Add company logo to cover page

This is the feature that makes enterprise buyers happy.

### 3.5 — Improve Chart Quality
Current known issues to fix:
- Line chart with daily time series is noisy — aggregate to weekly/monthly automatically
- Scatter plots with >1000 points need sampling (already flagged)
- Bar charts with many categories need horizontal layout
- Add a `heatmap` type for correlation matrices (very useful for analysts)
- Export charts as SVG not just PNG (crisper in PDF)

### 3.6 — Support More File Types
```python
ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls", ".tsv", ".json"]
```

Google Sheets URL import (paste a share link, it reads the sheet):
```bash
pip install gspread
```

This removes the biggest friction point for non-technical users.

### 3.7 — Report Sharing
Generate a public read-only URL for each report:
```
https://insightengine.in/share/abc12345
```

User can share with clients or teammates without them needing an account.
This is free viral marketing — every shared report is a product demo.

---

## Phase 4 — Monetization
**Timeline: 2 weeks after Phase 3 | Effort: Medium**

### 4.1 — Pricing Model

**Freemium** is the right model for this product:

| Tier | Price | Limits | Target |
|------|-------|--------|--------|
| Free | ₹0 | 3 reports/month, 1000 row limit, watermarked PDF | Students, trying users |
| Starter | ₹499/mo | 20 reports/month, 10k rows, no watermark | Freelancers, small teams |
| Pro | ₹1499/mo | Unlimited reports, 50k rows, custom branding, API access | Small businesses |
| Enterprise | Custom | Unlimited, white-label, SSO, SLA | Corporates |

### 4.2 — Payment Integration
**Razorpay** for Indian market (easiest integration, supports UPI):
```bash
pip install razorpay
```

Add a `subscriptions` table. Check user tier on every `/upload` request.

### 4.3 — Usage Tracking
Add usage metrics to the database:
- Reports generated per user per month
- Average processing time
- Most common file types and domains
- Failed report rate

This data tells you what to fix and what to charge for.

### 4.4 — Enforce Limits in Code
```python
def check_user_quota(user_id):
    usage = db.query("SELECT COUNT(*) FROM reports WHERE user_id=? AND created_at > NOW() - INTERVAL '30 days'", user_id)
    limit = TIER_LIMITS[user.tier]["reports_per_month"]
    if usage >= limit:
        raise QuotaExceededException("Upgrade your plan to generate more reports.")
```

### 4.5 — Referral Program
Give users 1 extra free report for every referral that signs up.
Costs you nothing, drives organic growth.

---

## Phase 5 — Scale and Grow
**Timeline: Ongoing**

### 5.1 — API Access (Pro tier feature)
Let developers integrate Insight Engine into their own apps:
```
POST /api/v1/reports
Authorization: Bearer {api_key}
Content-Type: multipart/form-data

→ Returns { report_id, status_url, estimated_time }
```

This opens a B2B channel — other SaaS products can embed your report generation.

### 5.2 — Increase Row Limit
With async processing, proper cloud storage, and chunked pandas reading:
- Starter: 50k rows
- Pro: 500k rows
- Enterprise: unlimited (streaming processing)

Use `pandas chunksize` parameter for large files:
```python
chunks = pd.read_csv(filepath, chunksize=10000)
df = pd.concat([chunk for chunk in chunks])
```

### 5.3 — LLM Provider Flexibility
Abstract the LLM calls behind a provider interface:
```python
class LLMProvider:
    def complete(self, prompt): raise NotImplementedError

class GroqProvider(LLMProvider): ...
class AnthropicProvider(LLMProvider): ...
class OpenAIProvider(LLMProvider): ...
```

Let Pro users bring their own API key (BYOK model) — reduces your LLM cost to zero for those users.

### 5.4 — Scheduled Reports
Let users connect a Google Sheet or upload a recurring file and get a report emailed every Monday morning.
```bash
pip install celery-beat
```

This is a sticky retention feature — once someone sets up a weekly report, they don't churn.

### 5.5 — White-label for Agencies
Let agencies resell Insight Engine under their own brand.
They pay you a flat monthly fee, their clients never see your brand.
This is high-margin B2B revenue with low support overhead.

---

## Tech Stack Evolution

| Phase | Backend | Frontend | Storage | Auth | Queue |
|-------|---------|----------|---------|------|-------|
| Now | Flask dev | HTML/CSS/JS | Local filesystem | None | None |
| Phase 1 | Flask + Gunicorn | HTML/CSS/JS | Local filesystem | None | Celery + Redis |
| Phase 2 | Flask + Gunicorn | HTML/CSS/JS | Cloudflare R2 + PostgreSQL | None | Celery + Redis |
| Phase 3 | Flask + Gunicorn | Tailwind + Jinja2 | R2 + PostgreSQL | Flask-Login | Celery + Redis |
| Phase 4 | Flask + Gunicorn | React (optional) | R2 + PostgreSQL | OAuth + JWT | Celery + Redis |
| Phase 5 | FastAPI | React | R2 + PostgreSQL + Redis Cache | OAuth + JWT + API Keys | Celery + Redis |

---

## Realistic Timeline

```
Week 1-2   │ Phase 0 + Phase 1  │ Fix critical issues, harden backend, write tests
Week 3     │ Phase 2            │ Deploy to Railway, custom domain, CI/CD
Week 4-7   │ Phase 3            │ Auth, dashboard, better frontend, more file types
Week 8-9   │ Phase 4            │ Razorpay, freemium tiers, usage tracking
Week 10+   │ Phase 5            │ API access, scale limits, scheduled reports
```

---

## Key Milestones

- [ ] **v0.2** — Phase 0 complete. Retry logic, parallel narrator, validator, cleanup.
- [ ] **v0.5** — Phase 1 complete. Gunicorn, job queue, rate limiting, tests passing.
- [ ] **v1.0** — Phase 2 complete. Live on real URL, cloud storage, CI/CD running.
- [ ] **v1.5** — Phase 3 complete. Auth, dashboard, report history, better frontend.
- [ ] **v2.0** — Phase 4 complete. Paying customers possible. Razorpay live.
- [ ] **v3.0** — Phase 5. API access, scheduled reports, white-label.

---

## What to Do Right Now (Today)

1. `git init` and push to GitHub if not already done
2. Implement Phase 0 fixes — 2 days of focused work
3. Write the three smoke tests
4. Create a Railway account and connect the repo

Everything else follows from those four steps.

---

## Resources

| Topic | Resource |
|-------|---------|
| Celery + Redis | `docs.celeryq.dev` |
| Railway deployment | `docs.railway.app` |
| Cloudflare R2 | `developers.cloudflare.com/r2` |
| Flask-Login | `flask-login.readthedocs.io` |
| Razorpay integration | `razorpay.com/docs/payments/payment-gateway` |
| Gunicorn config | `docs.gunicorn.org/en/stable/configure.html` |
| Tenacity retries | `tenacity.readthedocs.io` |
| pytest basics | `docs.pytest.org/en/stable/getting-started.html` |

---

*Built by Sparsh — Insight Engine v0.1 → v3.0*
