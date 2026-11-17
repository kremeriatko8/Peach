"""Cloud Run connects to Cloud SQL through a unix socket built from env parts."""

import pytest
from sqlalchemy.engine import make_url

from app.config import Settings


def test_cloud_sql_socket_url_is_built_from_parts():
    settings = Settings(
        instance_connection_name="proj:us-central1:peach-db",
        db_user="peach",
        db_password="p@ss/w:rd",
        db_name="peach",
    )
    url = make_url(settings.database_url)
    assert url.drivername == "postgresql+asyncpg"
    assert url.host is None
    assert url.password == "p@ss/w:rd"
    assert url.database == "peach"
    assert url.query["host"] == "/cloudsql/proj:us-central1:peach-db"


def test_cloud_sql_requires_credentials():
    with pytest.raises(ValueError):
        Settings(instance_connection_name="proj:us-central1:peach-db", db_user="peach")


def test_plain_database_url_is_untouched_without_instance():
    url = "postgresql+asyncpg://peach:peach@db:5432/peach"
    assert Settings(database_url=url).database_url == url
