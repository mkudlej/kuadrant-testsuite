"""
Conftest for performance tests
"""
import pytest
from hyperfoil import HyperfoilClient
from dynaconf import ValidationError

from testsuite.perf_utils import HyperfoilUtils
from testsuite.httpx.auth import HttpxOidcClientAuth


@pytest.fixture(scope='session')
def hyperfoil_client(testconfig):
    """Hyperfoil client"""
    try:
        return HyperfoilClient(testconfig['hyperfoil']['url'])
    except (KeyError, ValidationError) as exc:
        return pytest.skip(f"Hyperfoil configuration item is missing: {exc}")


@pytest.fixture(scope='module')
def hyperfoil_utils(hyperfoil_client, template, request):
    """Init of hyperfoil utils"""
    utils = HyperfoilUtils(hyperfoil_client, template)
    request.addfinalizer(utils.delete)
    utils.commit()
    return utils


@pytest.fixture(scope="module")
def rhsso_auth(rhsso):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(rhsso.get_token)


@pytest.fixture(scope='module')
def number_of_agents():
    """Number of spawned HyperFoil agents"""
    return 1
