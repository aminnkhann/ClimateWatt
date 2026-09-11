"""Tests for database schema initialization."""

from weather_energy.database.loader import initialize_database


class _Cursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, statement):
        self.statements.append(statement)


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True


def test_initialize_database_reads_packaged_schema():
    connection = _Connection()

    initialize_database(connection)

    statement = connection.cursor_instance.statements[0]

    assert "CREATE TABLE IF NOT EXISTS raw.weather_hourly" in statement
    assert "CREATE TABLE IF NOT EXISTS analytics.weather_energy_hourly" in (
        statement
    )
    assert connection.committed is True
