# Lab 9 — written answers

## Part 4. Think about it: Document AI vs a general LLM

Lab 6 parses a pasted agenda with an LLM (Bedrock Nova Lite) into structured items.

**Document AI (or Vision OCR) is the better tool when:**
- The input is a **scan, photo or PDF**, not text. OCR with layout, bounding boxes and
  per-field confidence is what it is built for; an LLM needs the text first anyway.
- The document type is **fixed and high-volume** (invoices, receipts, forms, IDs): a
  Form Parser or custom extractor gives the same schema every time, with confidence
  scores, at a predictable $1.50 per 1,000 pages (OCR) or $30 per 1,000 (Form Parser).
- You need **auditability**: where on the page each value came from, deterministic
  output, no hallucinated fields, and data residency guarantees.

**A general LLM is better when:**
- The input is **free text with no fixed layout**, like Peach's agendas: "10:00 intro
  (Anna), then budget ~20 min". There are no fields to locate, only meaning to extract.
- The schema **changes often**; a prompt edit is cheaper than training a custom extractor.
- You need **reasoning on top of extraction**: durations from times, normalising names,
  flagging contradictions. Document AI extracts; it does not interpret.
- Volume is low: a few hundred agendas cost cents in tokens.

Peach's case: pasted text, small volume, fuzzy structure → LLM, with schema
validation and grounding checks on the output (`app/ai/grounding.py`). If users
uploaded photographed paper agendas, the right pipeline would be **OCR first
(Document AI / Vision), LLM second**.

## Part 4. Link it to Lab 8: S3 + Glue crawler + Athena on Google Cloud

| Lab 8 on AWS | Google Cloud | What changes |
|---|---|---|
| S3 bucket with payment CSV/JSON files | **Cloud Storage** bucket (landing zone) | Same idea: cheap object storage, raw files. |
| Glue crawler (infers schema → Glue Data Catalog table) | **BigQuery** load job or **external table** with schema auto-detect; for transforms, **Dataflow** (e.g. the "Cloud Storage Text to BigQuery" template) | No crawler to schedule and re-run when files change; the schema lives with the BigQuery table. |
| Glue Data Catalog | BigQuery datasets/tables (Dataplex for a wider catalog) | The catalog is the warehouse itself. |
| Athena (SQL over S3, $5/TB scanned) | **BigQuery** (SQL, $6.25/TiB scanned, first 1 TiB/month free) | Native storage is columnar and managed; partitioning/clustering instead of hand-made Parquet + partition projection. |
| QuickSight (if used) | **Looker Studio** (free) | Free dashboards straight over BigQuery. |
| (cron / Step Functions) | Managed Service for Apache Airflow, or BigQuery scheduled queries | Scheduled queries cover the simple case without an Airflow environment. |

**What we no longer manage:**
- **Crawlers and their schedules**, and fixing crawler-inferred schemas when a file
  has a new column.
- **The Glue Data Catalog / table definitions** separate from the data.
- **The query results bucket** Athena needs (`s3://…/athena-results/`) and its lifecycle.
- **File layout for performance**: converting CSV to Parquet, choosing partition keys in
  S3 paths, `MSCK REPAIR TABLE` / partition projection. BigQuery stores columnar data
  and partitions it by a column.
- **Glue job DPUs** for transforms: Dataflow autoscales workers and shuts them down
  after the job; for most of Lab 8, plain SQL in BigQuery replaces the job entirely.
- **A BI server/licence**: Looker Studio is free.

What we still manage: IAM on datasets, cost control (bytes scanned: always select
columns and filter partitions, set a maximum bytes billed), and data retention.

## What we discuss in class

**1. Lock-in: what moved unchanged, what was rewritten, where is the lock-in?**
- **Unchanged:** all FastAPI routes, services, SQLAlchemy models, the five Alembic
  migrations, the Next.js frontend and its tests. Postgres is Postgres.
- **Small changes:** removed Mangum (`lambda_handler.py`), listen on `$PORT`, build the
  DB URL for the Cloud SQL unix socket (~30 lines in `config.py`), set the API base to
  same-origin for Firebase.
- **Rewritten:** all infrastructure (`infra/` → `gcp/`, a new Terraform root) and the
  deploy commands.
- **Not moved because it would be a rewrite:** the weekly report (Scheduler + SQS +
  S3 events + DynamoDB + SES), Cognito, Bedrock.
- **So the lock-in is in the managed services around compute**, and in data that has
  to be exported (user passwords in Cognito can't be exported at all). Compute in a
  container is portable; SQL data is portable with `pg_dump`. Event wiring and identity
  are not.

**2. Multicloud: good idea or only a migration state?**
For Peach it is a **migration state that is acceptable for a while**. It works because
the coupling is thin: the browser talks to Cognito (AWS) and the API (GCP) separately,
and the API only needs Cognito's public keys. Costs: cross-cloud calls add ~30 ms
round trip us-central1 ↔ us-east-1; **egress** is billed on both sides (AWS ~$0.09/GB,
GCP ~$0.12/GB to internet) and the report Lambda would need a public path to the
Cloud SQL data; **operations** double: two consoles, two IAM models, two Terraform
states, two budgets, two sets of on-call knowledge. Multicloud as a goal makes sense
for a big organisation (negotiating power, regulatory, best-of-breed AI/data); for a
small team it is usually the cost of a migration not yet finished.

**3. Scale to zero: when is giving up SQL worth ~$9 a month?**
Worth it when the data is **naturally document-shaped** and accessed by key (user
settings, session state, a log of events), the app is idle most of the time, and you
are starting fresh. A bad trade when the data is **relational** (Peach: meetings →
agendas, items with owners, reports aggregated with SQL), when you already have
migrations and SQL tests, or when reads per page are high (Firestore bills per
document read: a 500-document list page uses the daily free reads in 100 visits).
$9/month is about one hour of a developer's time; a data-layer rewrite is weeks.
Cheaper alternatives first: stop the instance when unused, or a serverless Postgres.

**4. Choosing a cloud: what actually decides?**
For hosting an API they are equivalent, so the deciding factors are, in order:
1. **What the team already knows and has running** (skills, existing accounts, IAM,
   CI). Migration cost dwarfs list-price differences at our scale.
2. **The data and AI services you need**: BigQuery + Looker Studio vs Athena +
   QuickSight; Gemini/Vertex vs Bedrock (both offer Claude).
3. **Price shape**, not price level: pay-per-awake-hour (Aurora) suits bursty use,
   flat instances (Cloud SQL) suit steady use (see `lab9-costs.md`).
4. **Credits and free tiers** ($300 GCP trial, AWS Educate, startup programs), which
   often decide a student or startup choice in practice.
5. Region, compliance and the customer's existing cloud.
