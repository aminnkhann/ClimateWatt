"""Static checks for the Level 3 Airflow DAG."""

import ast
from pathlib import Path


def test_weather_energy_daily_dag_is_parseable_and_thin():
    path = Path("dags/weather_energy_daily.py")
    tree = ast.parse(path.read_text())
    calls = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)]

    assert "weather_energy_daily" in path.read_text()
    assert "fetch_weather_task" in calls
    assert "fetch_prices_task" in calls
    assert "initialize_database_task" in calls
    assert "load_weather_raw_task" in calls
    assert "load_prices_raw_task" in calls
    assert "build_analytics_task" in calls
    assert "validate_analytics_task" in calls
    assert "SELECT " not in path.read_text()
