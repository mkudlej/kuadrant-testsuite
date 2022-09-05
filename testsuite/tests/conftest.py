"""Root conftest"""
from urllib.parse import urlparse

import pytest
from keycloak import KeycloakAuthenticationError

from testsuite.config import settings
from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift.envoy import Envoy
from testsuite.rhsso import RHSSO, Realm, RHSSOServiceConfiguration
from testsuite.utils import randomize, _whoami


@pytest.fixture(scope="session")
def testconfig():
    """Testsuite settings"""
    return settings


@pytest.fixture(scope="session")
def openshift(testconfig):
    """OpenShift client for the primary namespace"""
    client = testconfig["openshift"]
    if not client.connected:
        pytest.fail("You are not logged into Openshift or the namespace doesn't exist")
    return client


@pytest.fixture(scope="session")
def openshift2(testconfig):
    """OpenShift client for the secondary namespace located on the same cluster as primary Openshift"""
    client = testconfig["openshift2"]
    if client is None:
        pytest.skip("Openshift2 required but second_project was not set")
    if not client.connected:
        pytest.fail("You are not logged into Openshift or the namespace for Openshift2 doesn't exist")
    return client


@pytest.fixture(scope="session")
def rhsso_service_info(request, testconfig, blame):
    """
    Set up client for zync
    :return: dict with all important details
    """
    cnf = testconfig["rhsso"]
    try:
        rhsso = RHSSO(server_url=cnf["url"],
                      username=cnf["username"],
                      password=cnf["password"])
    except KeycloakAuthenticationError:
        return pytest.skip("Unable to login into SSO, please check the credentials provided")
    except KeyError as exc:
        return pytest.skip(f"SSO configuration item is missing: {exc}")

    realm: Realm = rhsso.create_realm(blame("realm"), accessTokenLifespan=24*60*60)

    if not testconfig["skip_cleanup"]:
        request.addfinalizer(realm.delete)

    client = realm.create_client(
        name=blame("client"),
        directAccessGrantsEnabled=True,
        publicClient=False,
        protocol="openid-connect",
        standardFlowEnabled=False)

    username = cnf["test_user"]["username"]
    password = cnf["test_user"]["password"]
    user = realm.create_user(username, password)

    return RHSSOServiceConfiguration(rhsso, realm, client, user, username, password)


@pytest.fixture(scope="session")
def blame(request):
    """Returns function that will add random identifier to the name"""
    def _blame(name: str, tail: int = 3) -> str:
        """Create 'scoped' name within given test

        This returns unique name for object(s) to avoid conflicts

        Args:
            :param name: Base name, e.g. 'svc'
            :param tail: length of random suffix"""

        nodename = request.node.name
        if nodename.startswith("test_"):  # is this always true?
            nodename = nodename[5:]

        context = nodename.lower().split("_")[0]
        if len(context) > 2:
            context = context[:2] + context[2:-1].translate(str.maketrans("", "", "aiyu")) + context[-1]

        if "." in context:
            context = context.split(".")[0]

        return randomize(f"{name[:8]}-{_whoami()[:8]}-{context[:9]}", tail=tail)
    return _blame


@pytest.fixture(scope="session")
def label(blame):
    """Session scope label for all resources"""
    return blame("testrun")


@pytest.fixture(scope="module")
def module_label(label):
    """Module scope label for all resources"""
    return randomize(label)


@pytest.fixture(scope="session")
def backend(request, openshift, blame, label):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(openshift, blame("httpbin"), label)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin


@pytest.fixture(scope="module")
def envoy(request, authorino, openshift, blame, backend, module_label):
    """Deploys Envoy that wire up the Backend behind the reverse-proxy and Authorino instance"""
    envoy = Envoy(openshift, authorino, blame("envoy"), module_label, backend.url)
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="session")
def wildcard_domain(openshift):
    """
    Wildcard domain of openshift cluster
    """
    hostname = urlparse(openshift.api_url).hostname
    return "*.apps." + hostname.split(".", 1)[1]
