locals {
  # Everything a fresh project needs, enabled from Terraform so it is reproducible.
  services = [
    "artifactregistry.googleapis.com",
    "firebasehosting.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
  ]

  api_image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.api.repository_id}/api:${var.api_image_tag}"
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)

  service = each.value
  # Turning an API off on destroy can break other things in the project.
  disable_on_destroy = false
}

# --- Artifact Registry (ECR counterpart) -----------------------------------

resource "google_artifact_registry_repository" "api" {
  location      = var.region
  repository_id = var.name
  format        = "DOCKER"
  description   = "Peach backend images"

  # Stay inside the 0.5 GB free tier: keep only the newest few images.
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "604800s"
    }
  }

  depends_on = [google_project_service.enabled]
}

# --- Cloud SQL for PostgreSQL (Aurora counterpart) -------------------------

resource "google_sql_database_instance" "db" {
  name             = "${var.name}-db"
  region           = var.region
  database_version = "POSTGRES_17"

  deletion_protection = var.db_deletion_protection

  settings {
    # db-f1-micro (shared core, 0.6 GB) only exists in the Enterprise edition;
    # PostgreSQL 16+ would otherwise default to Enterprise Plus.
    edition           = "ENTERPRISE"
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 10
    disk_autoresize   = false

    # ALWAYS = running, NEVER = stopped. Cloud SQL never pauses on its own.
    activation_policy = var.db_activation_policy

    backup_configuration {
      # Lab data only; backups would add storage cost.
      enabled = false
    }

    ip_configuration {
      # Public IP with no authorised networks: nothing can connect directly.
      # Cloud Run reaches it through the Cloud SQL connector, which authenticates
      # with IAM (roles/cloudsql.client) and encrypts the connection.
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }
  }

  depends_on = [google_project_service.enabled]
}

resource "google_sql_database" "app" {
  name     = var.name
  instance = google_sql_database_instance.db.name
}

resource "random_password" "db" {
  length = 32
  # Letters and digits only: the value ends up in a SQLAlchemy URL and in
  # Alembic's ini-style config, where % and friends need escaping.
  special = false
}

resource "google_sql_user" "app" {
  name     = var.name
  instance = google_sql_database_instance.db.name
  password = random_password.db.result
}

# --- Secret Manager: the database password, never in the repository --------

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.name}-db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db.result
}

# --- The API's own identity -------------------------------------------------
# Not the default compute service account (which starts with Editor), and no key.

resource "google_service_account" "api" {
  account_id   = "${var.name}-api"
  display_name = "Peach API (Cloud Run runtime)"

  depends_on = [google_project_service.enabled]
}

resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = google_service_account.api.member
}

# Scoped to this one secret, not the whole project.
resource "google_secret_manager_secret_iam_member" "api_db_password" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.api.member
}

# --- Cloud Run (Lambda + function URL counterpart) --------------------------

resource "google_cloud_run_v2_service" "api" {
  name     = "${var.name}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = 0
      max_instance_count = var.api_max_instances
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.db.connection_name]
      }
    }

    containers {
      image = local.api_image

      # Cloud Run sets PORT=8080; the entrypoint listens on it.
      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        # Request-based billing: CPU only while a request is in flight.
        cpu_idle          = true
        startup_cpu_boost = true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = google_sql_database_instance.db.connection_name
      }
      env {
        name  = "DB_NAME"
        value = google_sql_database.app.name
      }
      env {
        name  = "DB_USER"
        value = google_sql_user.app.name
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }
      env {
        name  = "COGNITO_AUTHORITY"
        value = var.cognito_authority
      }
      env {
        name  = "COGNITO_CLIENT_ID"
        value = var.cognito_client_id
      }
      env {
        name  = "COGNITO_JWKS_JSON"
        value = var.cognito_jwks_json
      }

      # Liveness endpoint that touches no dependencies; migrations run before it answers.
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 0
        period_seconds        = 5
        timeout_seconds       = 3
        failure_threshold     = 24
      }
    }
  }

  depends_on = [
    google_project_iam_member.api_cloudsql_client,
    google_secret_manager_secret_iam_member.api_db_password,
    google_secret_manager_secret_version.db_password,
  ]
}

# Public: the API checks Cognito access tokens itself on every protected route,
# and /health is meant to be public. Firebase Hosting also needs this to proxy /api/**.
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
