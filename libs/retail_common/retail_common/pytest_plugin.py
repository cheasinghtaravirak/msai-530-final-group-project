"""pytest plugin for the services: `addopts = -p retail_common.pytest_plugin` in pytest.ini.

Service DB users may not create databases (infra/postgres/init.sh), so tests run against the
service's own database. Each test runs in a transaction that is rolled back, so tests must not
use `transaction=True` and should use their own keys (SKUs, branch IDs) to stay clear of live rows.
"""

import pytest


@pytest.fixture(scope="session")
def django_db_setup():
    pass
