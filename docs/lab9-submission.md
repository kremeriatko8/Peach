# Lab 9: здача (альтернативний шлях, без GCP-акаунта)

Free Trial на Google Cloud не вдалося створити, тому частина Lab 9, яка вимагає
розгортання у GCP, не виконана. Здається альтернативний варіант з лабораторної:
Terraform і ADR, вартість, локальна перевірка образу і демо без рахунку.

## Що здається

| Пункт лаби | Де | Статус |
|---|---|---|
| Коміт з `gcp/` Terraform і ADR | коміт `83c4dc6`, гілка `lab9-gcp` | готово |
| ADR з рішеннями Частини 1 | `docs/adr/0008-gcp-service-choices.md` | готово |
| Вивід `terraform init` / `validate` / `plan` | нижче, розділ «Докази» | **треба зняти на ноутбуці** |
| Таблиця вартості (Частина 3) | `docs/lab9-costs.md` | готово, перевірити в калькуляторах |
| Демо Частини 4 (BigQuery, Looker Studio, OCR) | `docs/lab9-part4-demos.ipynb` | **треба запустити в Colab і зробити скріншоти** |
| Відповіді на питання Частин 1, 3, 4 | `docs/lab9-answers.md` | готово |

Гілка з усім: https://github.com/kremeriatko8/Peach/tree/lab9-gcp

## Докази

### Terraform (`gcp/`)

```
$ terraform -chdir=gcp init -backend=false
<вставити вивід>

$ terraform -chdir=gcp validate
<вставити вивід>

$ terraform -chdir=gcp plan
<вставити вивід, або помилку, якщо план вимагає Google-облікових даних>
```

### Образ API локально (замість URL проєкту в GCP)

```
$ docker compose up -d --build db backend
$ curl -fsS http://localhost:8000/health
<вставити вивід>
```

## Демо Частини 4

- Colab-ноутбук: `docs/lab9-part4-demos.ipynb` (завантажити в Colab, замінити `PROJECT_ID`, Run all).
- Посилання на копію ноутбука в Colab: <вставити>
- BigQuery-запит з обсягом байтів: <скріншот>
- Looker Studio, публічний звіт: <посилання і скріншот>
- OCR (Vision API або Document AI): <не зроблено; вирішити, чи робити>

## Що перевірено і як

- Синтаксис HCL у `gcp/*.tf` перевірено парсером `python-hcl2`. Семантичну перевірку (`terraform validate`) у цьому середовищі не запускали: Terraform тут не встановлений, а завантажити його не вийшло.
- Pandas-частина ноутбука перевірена на вихідному CSV Our World in Data (топ-10 за 2021 рік отримано).
- BigQuery-частини ноутбука в цьому середовищі не запускались: немає доступу до BigQuery.
- Таблиці вартості розраховані вручну з цін зі сторінки лаби. Їх треба звірити з Pricing Calculator.
