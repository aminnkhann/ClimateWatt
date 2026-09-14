"""Static safety checks for the local Docker Compose configuration."""

from pathlib import Path


def test_airflow_compose_configuration_handles_city_settings_and_database_urls():
    compose = Path("docker-compose.yml").read_text()

    assert "env_file: &airflow-city-env" in compose
    assert compose.count("env_file: *airflow-city-env") == 2
    assert "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN_CMD" in compose
    assert "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:" not in compose
    assert "DATABASE_URL:" not in compose


def test_airflow_migration_failure_is_not_masked_by_user_creation():
    compose = Path("docker-compose.yml").read_text()

    assert 'bash -c "airflow db migrate &&' in compose
    assert "(airflow users create" in compose
