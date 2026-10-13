# Demo Script (about 5 minutes)

A walk-through for showing FinTrace to someone, for example in an interview. It uses the Docker
stack and the demo accounts. Every step below was run against the stack while writing it.

## Before you start

```powershell
Copy-Item .env.example .env
# Edit .env: set POSTGRES_PASSWORD, FINTRACE_JWT_SECRET (32+ random characters)
# and FINTRACE_DEMO_PASSWORD (12+ characters, local only).
docker compose up -d --build --wait
docker compose exec api python -m app.cli demo-seed
```

`demo-seed` creates three accounts (`demo.analyst@`, `demo.senior@` and `demo.admin@example.com`,
all with your `FINTRACE_DEMO_PASSWORD`), imports the 5,000-row synthetic sample, makes sure a model
is active, scores everything and opens one example case. It is safe to run again.

Which model it uses:

- If you trained on PaySim (README, "Train the model"), copy the model in first and the demo shows
  real PaySim scores:
  ```powershell
  docker compose cp ml/artifacts/current api:/app/ml/artifacts/
  docker compose exec api python -m app.cli sync-model
  ```
- Otherwise `demo-seed` trains a **synthetic smoke-test model** on the sample. The dashboard says so
  on the overview and model pages. Its numbers are not results; say that out loud.

Open http://localhost:8080.

## The walk-through

| # | Show | Say |
|---|---|---|
| 1 | Sign-in page | "A prototype on synthetic data. Scores are triage signals for a person, not verdicts." |
| 2 | Sign in as `demo.analyst@example.com`. **Overview** | "The dark panel is the open-alert workload, split by priority. Critical means the model and at least two monitoring rules agree. The histogram is the latest score for every transaction, log scale, with the alert threshold marked." |
| 3 | **Alert queue**, sorted by priority | "Each alert carries its score, the rules that fired and reason codes. Filters live in the URL, so a view can be shared." |
| 4 | Set **Case** to "Not in a case" and open the top alert (the example case already holds two alerts) | "Why it was flagged: the score, the model version that produced it, and each rule hit with the numbers behind it." Click **Assign to me**, then **Start review**. |
| 5 | **Open a case** from the alert | "Alerts are grouped into cases. Notes are append-only. Every change lands in the timeline and the audit log." Add a short note. |
| 6 | **Transactions**, filter risk level = critical, open one | "Every assessment is kept, with the model version, so an old decision can be explained later." |
| 7 | **Model evaluation** | With the synthetic demo model, point at the "not results" warning and talk about the PaySim report instead. "It leads with the caveats. On PaySim, a transfer of exactly the full balance is always fraud, so the 0.9999 average precision mostly measures that quirk. Without balance features it is 0.629. I report both." |
| 8 | Sign out, sign in as `demo.senior@example.com`. Open the case | "Only a senior analyst can close a case, and only with a decision and a written rationale." Record a decision. |
| 9 | **Audit log** | "Who did what and when, written in the same database transaction as the change itself." |
| 10 | Optional: **Light theme** in the sidebar | The light "paper" theme, remembered per browser. |

## Questions people ask

- **Is this production-ready?** No. See [LIMITATIONS.md](LIMITATIONS.md).
- **Why is the score so high?** The PaySim signature above. [MODEL_REPORT.md](MODEL_REPORT.md)
  has the diagnostic run without it.
- **How do you stop training/serving skew?** The API and the training pipeline share one feature
  module, and a test checks that their scores match on 5,000 transactions.
- **What happens without a model?** Scoring returns `503 MODEL_NOT_AVAILABLE` with the commands to
  fix it. It never makes up a score.

## Reset

`docker compose down -v` deletes the containers **and** the database and model volumes. Run
`demo-seed` again after `up` to start fresh.
