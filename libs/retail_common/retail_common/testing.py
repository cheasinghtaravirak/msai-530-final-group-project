"""Test setup shared by the services. Each service's tests/conftest.py imports both names:

    from retail_common.testing import django_db_setup, pytest_runtest_setup  # noqa: F401

Service DB users may not create databases (infra/postgres/init.sh), so tests run against the
service's own database. Each test runs in a transaction that is rolled back, and tests should use
their own keys (SKUs, branch IDs) to stay clear of live rows.
"""

import pytest
from pytest_django.fixtures import validate_django_db

TRANSACTIONAL_FIXTURES = {"transactional_db", "live_server", "django_db_reset_sequences"}


@pytest.fixture(scope="session")
def django_db_setup():
    pass


# A hook, not an autouse fixture: pytest-django's own autouse fixture opens the TransactionTestCase
# before any conftest fixture runs, and a later failure would still flush the database on teardown.
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    marker = item.get_closest_marker("django_db")
    transaction, reset_sequences, *_ = validate_django_db(marker) if marker else (False, False)
    fixtures = TRANSACTIONAL_FIXTURES.intersection(getattr(item, "fixturenames", ()))
    if transaction or reset_sequences or fixtures:
        pytest.fail(
            "Transactional tests are not allowed: tests run against the service's live database, "
            "and Django flushes every table after a transactional test. Use plain django_db instead.",
            pytrace=False,
        )
