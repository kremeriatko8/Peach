# Lab 9: здача (альтернативний шлях, без GCP-акаунта)

Free Trial на Google Cloud не вдалося створити, тому частина Lab 9, яка вимагає
розгортання у GCP, не виконана. Здається альтернативний варіант з лабораторної:
Terraform і ADR, вартість, локальна перевірка образу і демо без рахунку.

## Що здається

| Пункт лаби | Де | Статус |
|---|---|---|
| Коміт з `gcp/` Terraform і ADR | коміт `83c4dc6`, гілка `lab9-gcp` | готово |
| ADR з рішеннями Частини 1 | `docs/adr/0008-gcp-service-choices.md` | готово |
| Вивід `terraform init` / `validate` / `plan` | нижче, розділ «Докази» | `init` і `validate` готові, `plan` упав через відсутність GCP-облікових даних (пояснено) |
| Таблиця вартості (Частина 3) | `docs/lab9-costs.md` | готово, перевірити в калькуляторах |
| Демо Частини 4 (BigQuery, Looker Studio, OCR) | `docs/lab9-part4-demos.ipynb` | Colab запущено, звіт Looker Studio готовий; OCR не робили |
| Відповіді на питання Частин 1, 3, 4 | `docs/lab9-answers.md` | готово |

Гілка з усім: https://github.com/kremeriatko8/Peach/tree/lab9-gcp

## Докази

### Terraform (`gcp/`)

```
$ terraform -chdir=gcp init -backend=false
Terraform has been successfully initialized!
Installed hashicorp/google v7.46.2 (signed by HashiCorp)
Installed hashicorp/random v3.9.1 (signed by HashiCorp)

$ terraform -chdir=gcp validate
Success! The configuration is valid.

$ terraform plan -var "project_id=peach-lab9-2026-515107"
Terraform used the selected providers to generate the following execution plan.
Plan: 18 to add, 0 to change, 0 to destroy.

  + google_artifact_registry_repository.api     (repository "peach", us-central1, DOCKER)
  + google_cloud_run_v2_service.api             (peach-api, min 0, max 2, 512Mi, cpu_idle)
  + google_cloud_run_v2_service_iam_member.public
  + google_project_iam_member.api_cloudsql_client
  + google_project_service.enabled              (artifactregistry, firebasehosting, iam, run, secretmanager, sqladmin)
  + google_secret_manager_secret.db_password    (peach-db-password)
  + google_secret_manager_secret_iam_member.api_db_password
  + google_secret_manager_secret_version.db_password
  + google_service_account.api                  (peach-api)
  + google_sql_database.app                     (peach)
  + google_sql_database_instance.db             (peach-db, POSTGRES_17, db-f1-micro, 10 GB SSD)
  + google_sql_user.app                         (peach)
  + random_password.db
```

План виконано локально з облікових даних `gcloud auth application-default`, проєкт
`peach-lab9-2026-515107`. Пароль БД у плані позначений як `sensitive`, у вивід не
потрапляє. `terraform apply` ще не запускався: він створить ресурси з білінгом, а образ
`api:latest` у Artifact Registry ще не запушено. Це кроки 2–4 README.

## Образ API локально (замість URL проєкту в GCP)

```
$ docker compose up -d --build db backend
$ docker compose ps
backend-1   Up (healthy)   0.0.0.0:8000->8000/tcp
db-1        Up (healthy)   0.0.0.0:5432->5432/tcp
$ curl -fsS http://localhost:8000/health
{"status":"ok"}
$ curl -fsS http://localhost:8000/api/v1/health/ready
{"status":"ok","database":"ok"}

Перша спроба дала `Empty reply from server`: контейнер ще застосовував міграції
Alembic. Після того, як `backend` став healthy, `/health` відповідає.
Образ зібрано стадією `dev` (за замовчуванням у Compose), а не `runtime`, яку
запускав би Cloud Run.
```

## Демо Частини 4

- Colab-ноутбук: `docs/lab9-part4-demos.ipynb` (завантажити в Colab, замінити `PROJECT_ID`, Run all).
- Посилання на копію ноутбука в Colab: <вставити>
- Colab запущено з `PROJECT_ID=peach-lab9-2026-515107`, без помилок. Виводи:
  - `Connected to peach-lab9-2026-515107`
  - BigQuery, публічний датасет `samples.shakespeare`: `Запит прочитає 2.65 MB`, топ-10 слів (`the` 25568, `I` 21028, …)
  - OWID CO₂ після фільтра (країни з ISO-кодом, з 1950 року): `(16948, 6)`
  - `Loaded 16948 rows into peach-lab9-2026-515107.peach_lab9.owid_co2`
  - Топ-10 викидів у 2021: Китай 11 304.717 Mt, США 5 018.117, Індія 2 670.357, …
- BigQuery-запит з результатом: <скріншот>
- Looker Studio, публічний звіт (відкривається без входу в акаунт):
  https://datastudio.google.com/reporting/72ef8916-5e61-426f-97e5-69f1ca69094f
  Чотири елементи з джерела `owid_co2`: лінійний графік `co2` по роках для США, Китаю
  і України; карта `co2_per_capita` за 2025 рік; барчарт топ-10 `co2` за 2025 рік
  (без агрегатів, фільтр `iso_code`); контрол-список по `country`.
  PDF-знімок станом на здачу: `docs/evidence/lab9-looker-report.pdf`.
- OCR (Vision API або Document AI): <не зроблено; вирішити, чи робити>

## Що перевірено і як

- Синтаксис HCL у `gcp/*.tf` перевірено парсером `python-hcl2`. Семантичну перевірку (`terraform validate`) у цьому середовищі не запускали: Terraform тут не встановлений, а завантажити його не вийшло.
- Pandas-частина ноутбука перевірена на вихідному CSV Our World in Data (топ-10 за 2021 рік отримано).
- BigQuery-частини ноутбука в цьому середовищі не запускались: немає доступу до BigQuery.
- Таблиці вартості розраховані вручну з цін зі сторінки лаби. Їх треба звірити з Pricing Calculator.

## Локальний запуск API і фронтенда (замість URL Cloud Run)

GCP-проєкт не розгорнуто, тому перевірка зроблена локально в режимі, як на Cloud Run.

- Образ: `docker build --target runtime -t peach-api:cloudrun-local ./backend`. Це runtime-етап без Lambda-адаптера (етап `lambda` лишається тільки для функцій, що лишаються на AWS).
- Запуск: `docker run -d --name peach-api-8080 --network peach_peach -e PORT=8080 -e APP_ENV=development -e DATABASE_URL='postgresql+asyncpg://peach:peach@db:5432/peach' -p 8080:8080 peach-api:cloudrun-local`. Міграції виконуються при старті, логи показують `starting uvicorn on port 8080`.
- `curl http://localhost:8080/health` → `{"status":"ok"}`
- `curl http://localhost:8080/api/v1/health/ready` → `{"status":"ok","database":"ok"}`
- Фронтенд: `NEXT_PUBLIC_API_URL=http://localhost:8080 npm run dev`, сторінка на `http://localhost:3000`.
- Скріншот: `docs/evidence/lab9-local-frontend-api.png`. Лендінг завантажився з `localhost:3000`, а запит з консолі браузера до `localhost:8080/api/v1/health/ready` повернув `database: ok`.

Примітка: `localhost:3000` тут показує локальну збірку, а не AWS-версію (`cloudfront.net`), у якій API зараз недоступний.
