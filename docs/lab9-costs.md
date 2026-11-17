# Lab 9, Part 3 — Peach's core on AWS vs Google Cloud

On-demand list prices in USD, 730 h/month, from LAB9.md (checked 2026-11-05): AWS
us-east-1, GCP us-central1. Aurora ACU-hour price is the one used in Lab 4 / README
($0.12 per ACU-hour). Only the **core** is compared: frontend, API, database. Sign-in,
reports, parser and SES stay on AWS in both columns, so they cancel out.

## Reference: nobody uses it for a month

| Piece | AWS (as deployed) | Google Cloud (`gcp/`) |
|---|---|---|
| Frontend + CDN + HTTPS | CloudFront Free plan, WAF included → $0 | Firebase Hosting free → $0 |
| API | Lambda (arm64, 512 MB), idle → $0 | Cloud Run, min 0 → $0 |
| Database compute | Aurora, paused → $0 | Cloud SQL db-f1-micro running, 730 h × $0.0105 → **$7.67** |
| Database storage | ~1 GB × $0.10 → $0.10 | 10 GB SSD × $0.17 → $1.70 |
| Registry, secrets, logs | ECR + logs ≈ $0.20 | ≈ 96 MB image × 3 kept < 0.5 GB; 1 secret; logs < 50 GiB → $0 |
| **Total** | **≈ $0.30** | **≈ $9.37**, or **$1.70** with the instance stopped |

## Assumptions

- **Aurora** min 0 / max 1 ACU, auto-pause after 5 min idle. Awake at ~0.5 ACU under
  light load ($0.06/h), 1 ACU under sustained load ($0.12/h). Each session adds a 5-min tail.
- **Cloud SQL** db-f1-micro, $0.0105/h while running; storage always billed. Two ways
  to run it: *always on*, or *stopped outside use* (`db_activation_policy`).
- **Free tiers used:** Lambda 1M requests + 400k GB-s/month (always free); Cloud Run 2M
  requests, 180k vCPU-s, 360k GiB-s; Firebase Hosting 10 GB stored, 360 MB/day out;
  CloudFront Free plan; Secret Manager 6 versions / 10k accesses (Cloud Run reads the
  secret once per instance start); Artifact Registry 0.5 GB; Cloud Logging 50 GiB.
- **API traffic:** demos and office hours stay well inside every free tier.
  *Busy 24/7* = 1 request/s on average → 2.63M requests/month, 100 ms each, 1 vCPU /
  512 MiB on Cloud Run, 512 MB on Lambda. Static traffic stays under 360 MB/day.
- Egress for small JSON responses is ignored (< 1 GB/month).

## Four traffic profiles

| Profile | Use | AWS: Aurora | AWS: other | **AWS total** | GCP: Cloud SQL always on | GCP: Cloud SQL stopped outside use | GCP: Cloud Run | **GCP total** (always on / stopped) |
|---|---|---|---|---|---|---|---|---|
| Nobody | 0 h | $0 | $0.30 | **$0.30** | $9.37 | $1.70 | $0 | **$9.37 / $1.70** |
| Class demos | 10 × 2 h = 20 h (≈ 21 h awake) | 21 × $0.06 = $1.26 | $0.30 | **$1.56** | $9.37 | 20 × $0.0105 + $1.70 = $1.91 | $0 | **$9.37 / $1.91** |
| Office hours | 8 h × 22 d = 176 h (≈ 178 h awake) | 178 × $0.06 = $10.68 | $0.30 | **$10.98** | $9.37 | 176 × $0.0105 + $1.70 = $3.55 | $0 | **$9.37 / $3.55** |
| Busy 24/7 | 730 h, 2.63M req | 730 × $0.12 = $87.60 (at 0.5 ACU: $43.80) | $0.30 + Lambda $0.33 | **$88.23** ($44.43) | $9.37 | — (can't stop) | $2.24 | **$11.61** |

Lambda busy: (2.63M − 1M) × $0.20/M = $0.33; GB-s 131k < 400k free.
Cloud Run busy: (2.63M − 2M) × $0.40/M = $0.25 + (263k − 180k) vCPU-s × $0.000024 = $1.99;
GiB-s 131k < 360k free → $2.24. If db-f1-micro (0.6 GB, shared core) is too small for
busy traffic, db-g1-small adds 730 × ($0.035 − $0.0105) = $17.89 → **GCP ≈ $29.50**, still
cheaper than Aurora at 1 ACU.

## Which cloud is cheaper, and which line decides it

| Profile | Cheaper | Deciding line |
|---|---|---|
| Nobody | **AWS** ($0.30 vs $1.70 even with Cloud SQL stopped) | DB: Aurora pauses to $0; Cloud SQL still bills its 10 GB SSD minimum while stopped |
| Class demos | **AWS** ($1.56 vs $1.91 stopped / $9.37 always on) | DB compute: Aurora bills only ~21 awake hours, automatically |
| Office hours | **GCP** ($9.37 always on, $3.55 stopped vs $10.98) | DB compute: past ≈ 150 awake hours/month (($9.37 − $0.30) ÷ $0.06), a flat always-on instance beats ACU-hours |
| Busy 24/7 | **GCP** ($11.61 vs $44–88) | DB compute: 1 ACU-hour costs 11× a db-f1-micro hour |

**The single line is database compute in every profile.** Frontend and API are $0 or
cents on both clouds. Aurora is pay-per-awake-hour at a high rate; Cloud SQL is a
flat low rate that never stops by itself. Low or bursty use → AWS; steady use → GCP.
Stopping Cloud SQL by hand closes most of the gap at low use, but it is a human
remembering to do it, not a platform feature.

## The GCP equivalent of the "Aurora kept awake" trap

On AWS the trap is that Aurora only saves money while *paused*, and anything holding a
connection open (a pooled connection in a warm Lambda, a health check that queries the
DB, a dashboard) keeps it at ≥ 0.5 ACU around the clock: ≈ $44–88/month instead of cents.

On GCP:

1. **Cloud SQL is "kept awake" by default.** There's no pause at all, so the trap is not
   a stray connection but forgetting to stop it: $7.67/month idle, and the most common
   surprise on a student bill. Stopping still leaves $1.70 of storage; only
   `terraform destroy` gets to $0.
2. **Cloud Run kept awake.** `min_instance_count = 1` or instance-based billing
   (`cpu_idle = false`, "CPU always allocated") turns a $0 idle API into one billed
   every second: 2.63M vCPU-s + 1.3M GiB-s ≈ **up to ~$60/month** at LAB9's rates.
   We keep min 0 and `cpu_idle = true`. Pings (uptime checks, schedulers) are harmless
   with request-based billing: they cost per request, not per hour.
3. **Something that starts the database.** If a Cloud Scheduler job or a script patches
   the instance back to `ALWAYS` (or someone runs `terraform apply` with the default),
   the instance runs until someone notices.
