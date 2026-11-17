output "api_url" {
  description = "Cloud Run URL of the API."
  value       = google_cloud_run_v2_service.api.uri
}

output "api_service_name" {
  description = "Cloud Run service id, used by the Firebase /api/** rewrite."
  value       = google_cloud_run_v2_service.api.name
}

output "image_repository" {
  description = "Where to push the backend image."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.api.repository_id}"
}

output "db_instance" {
  description = "Cloud SQL instance name (for gcloud sql instances patch)."
  value       = google_sql_database_instance.db.name
}

output "db_connection_name" {
  description = "project:region:instance, mounted at /cloudsql/<this> in Cloud Run."
  value       = google_sql_database_instance.db.connection_name
}

output "db_password_secret" {
  description = "Secret Manager secret holding the database password (the value is not output)."
  value       = google_secret_manager_secret.db_password.secret_id
}

output "api_service_account" {
  description = "Identity the API runs as."
  value       = google_service_account.api.email
}
