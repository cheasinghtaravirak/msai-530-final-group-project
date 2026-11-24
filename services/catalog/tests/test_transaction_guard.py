from types import SimpleNamespace

import pytest

from retail_common import testing


def item(marker=None, fixturenames=()):
    return SimpleNamespace(fixturenames=list(fixturenames), get_closest_marker=lambda name: marker)


@pytest.mark.parametrize(
    "transactional",
    [
        item(pytest.mark.django_db(transaction=True).mark),
        item(pytest.mark.django_db(True).mark),
        item(pytest.mark.django_db(reset_sequences=True).mark),
        item(fixturenames=["transactional_db"]),
        item(fixturenames=["live_server"]),
    ],
)
def test_transactional_tests_fail_before_touching_the_database(transactional):
    with pytest.raises(pytest.fail.Exception, match="Transactional tests are not allowed"):
        testing.pytest_runtest_setup(transactional)


def test_rolled_back_tests_run():
    testing.pytest_runtest_setup(item(pytest.mark.django_db.mark, ["db"]))
    testing.pytest_runtest_setup(item())
