# Copyright 2013 Donald Stufft
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os.path
import textwrap

import pretend
import pytest
import requests

from twine import exceptions
from twine import utils

from . import helpers


def test_get_config(tmpdir):
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    with open(pypirc, "w") as fp:
        fp.write(
            textwrap.dedent(
                """
            [distutils]
            index-servers = pypi

            [pypi]
            username = testuser
            password = testpassword
        """
            )
        )

    assert utils.get_config(pypirc) == {
        "pypi": {
            "repository": utils.DEFAULT_REPOSITORY,
            "username": "testuser",
            "password": "testpassword",
        },
    }


def test_get_config_no_distutils(tmpdir):
    """
    Even if the user hasn't set PyPI has an index server
    in 'index-servers', default to uploading to PyPI.
    """
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    with open(pypirc, "w") as fp:
        fp.write(
            textwrap.dedent(
                """
            [pypi]
            username = testuser
            password = testpassword
        """
            )
        )

    assert utils.get_config(pypirc) == {
        "pypi": {
            "repository": utils.DEFAULT_REPOSITORY,
            "username": "testuser",
            "password": "testpassword",
        },
        "testpypi": {
            "repository": utils.TEST_REPOSITORY,
            "username": None,
            "password": None,
        },
    }


def test_get_config_no_section(tmpdir):
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    with open(pypirc, "w") as fp:
        fp.write(
            textwrap.dedent(
                """
            [distutils]
            index-servers = pypi foo

            [pypi]
            username = testuser
            password = testpassword
        """
            )
        )

    assert utils.get_config(pypirc) == {
        "pypi": {
            "repository": utils.DEFAULT_REPOSITORY,
            "username": "testuser",
            "password": "testpassword",
        },
    }


def test_get_config_override_pypi_url(tmpdir):
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    with open(pypirc, "w") as fp:
        fp.write(
            textwrap.dedent(
                """
            [pypi]
            repository = http://pypiproxy
        """
            )
        )

    assert utils.get_config(pypirc)["pypi"]["repository"] == "http://pypiproxy"


def test_get_config_missing(tmpdir):
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    assert utils.get_config(pypirc) == {
        "pypi": {
            "repository": utils.DEFAULT_REPOSITORY,
            "username": None,
            "password": None,
        },
        "testpypi": {
            "repository": utils.TEST_REPOSITORY,
            "username": None,
            "password": None,
        },
    }


def test_empty_userpass(tmpdir):
    """
    Empty username and password may be supplied to suppress
    prompts. See #426.
    """
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    with open(pypirc, "w") as fp:
        fp.write(
            textwrap.dedent(
                """
            [pypi]
            username=
            password=
        """
            )
        )

    config = utils.get_config(pypirc)
    pypi = config["pypi"]

    assert pypi["username"] == pypi["password"] == ""


def test_get_repository_config_missing(tmpdir):
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    repository_url = "https://notexisting.python.org/pypi"
    exp = {
        "repository": repository_url,
        "username": None,
        "password": None,
    }
    assert utils.get_repository_from_config(pypirc, "foo", repository_url) == exp
    assert utils.get_repository_from_config(pypirc, "pypi", repository_url) == exp
    exp = {
        "repository": utils.DEFAULT_REPOSITORY,
        "username": None,
        "password": None,
    }
    assert utils.get_repository_from_config(pypirc, "pypi") == exp


def test_get_repository_config_invalid_scheme(tmpdir):
    """Test if we get an URL with a invalid scheme"""
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    with pytest.raises(
        exceptions.UnreachableRepositoryURLDetected,
        match=r"Invalid repository URL: "
        r"scheme was required to be one of \['http', 'https'\] but was 'ftp'.",
    ):
        utils.get_repository_from_config(pypirc, "foo.bar", "ftp://test.pypi.org")


def test_get_repository_config_missing_components(tmpdir):
    """Test if we get an URL with missing components"""
    pypirc = os.path.join(str(tmpdir), ".pypirc")

    with pytest.raises(
        exceptions.UnreachableRepositoryURLDetected,
        match="Invalid repository URL: host was required but missing.",
    ):
        utils.get_repository_from_config(pypirc, "foo.bar", "https:/")

    with pytest.raises(
        exceptions.UnreachableRepositoryURLDetected,
        match="Invalid repository URL: scheme was required but missing.",
    ):
        utils.get_repository_from_config(pypirc, "foo.bar", "//test.pypi.org")

    with pytest.raises(
        exceptions.UnreachableRepositoryURLDetected,
        match="Invalid repository URL: host, scheme were required but missing.",
    ):
        utils.get_repository_from_config(pypirc, "foo.bar", "foo.bar")


def test_get_repository_config_missing_config(tmpdir):
    """Test if a invalid section is being looked for in the config file"""
    pypirc = os.path.join(str(tmpdir), ".pypirc")
    with pytest.raises(exceptions.InvalidConfiguration):
        utils.get_repository_from_config(pypirc, "foobar")


def test_get_config_deprecated_pypirc():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    deprecated_pypirc_path = os.path.join(tests_dir, "fixtures", "deprecated-pypirc")

    assert utils.get_config(deprecated_pypirc_path) == {
        "pypi": {
            "repository": utils.DEFAULT_REPOSITORY,
            "username": "testusername",
            "password": "testpassword",
        },
        "testpypi": {
            "repository": utils.TEST_REPOSITORY,
            "username": "testusername",
            "password": "testpassword",
        },
    }


@pytest.mark.parametrize(
    ("cli_value", "config", "key", "strategy", "expected"),
    (
        ("cli", {}, "key", lambda: "fallback", "cli"),
        (None, {"key": "value"}, "key", lambda: "fallback", "value"),
        (None, {}, "key", lambda: "fallback", "fallback"),
    ),
)
def test_get_userpass_value(cli_value, config, key, strategy, expected):
    ret = utils.get_userpass_value(cli_value, config, key, strategy)
    assert ret == expected


@pytest.mark.parametrize(
    ("env_name", "default", "environ", "expected"),
    [
        ("MY_PASSWORD", None, {}, None),
        ("MY_PASSWORD", None, {"MY_PASSWORD": "foo"}, "foo"),
        ("URL", "https://example.org", {}, "https://example.org"),
        ("URL", "https://example.org", {"URL": "https://pypi.org"}, "https://pypi.org"),
    ],
)
def test_default_to_environment_action(env_name, default, environ, expected):
    option_strings = ("-x", "--example")
    dest = "example"
    with helpers.set_env(**environ):
        action = utils.EnvironmentDefault(
            env=env_name, default=default, option_strings=option_strings, dest=dest,
        )
    assert action.env == env_name
    assert action.default == expected


@pytest.mark.parametrize(
    "repo_url", ["https://pypi.python.org", "https://testpypi.python.org"]
)
def test_check_status_code_for_deprecated_pypi_url(repo_url):
    response = pretend.stub(status_code=410, url=repo_url)

    # value of Verbose doesn't matter for this check
    with pytest.raises(exceptions.UploadToDeprecatedPyPIDetected):
        utils.check_status_code(response, False)


@pytest.mark.parametrize(
    "repo_url", ["https://pypi.python.org", "https://testpypi.python.org"],
)
def test_check_status_code_for_missing_status_code(capsys, repo_url):
    """Test if the status code returned is not an explicitly checked one"""
    response = pretend.stub(
        status_code=403,
        url=repo_url,
        raise_for_status=pretend.raiser(requests.HTTPError),
        text="Forbidden",
    )

    with pytest.raises(requests.HTTPError):
        utils.check_status_code(response, True)

    # Different messages are printed based on the verbose level
    captured = capsys.readouterr()
    assert captured.out == "Content received from server:\nForbidden\n"

    with pytest.raises(requests.HTTPError):
        utils.check_status_code(response, False)

    captured = capsys.readouterr()
    assert captured.out == "NOTE: Try --verbose to see response content.\n"
