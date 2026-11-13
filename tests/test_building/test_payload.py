"""Tests for VREPayloadBuilder — building VREPayload from ROCrate dict."""

import pytest

from vre_rocrate import VREPayloadBuilder, RuntimePlatform
from conftest import example_crate

BUILDER_CASES = [
    ("galaxy", "https://galaxyproject.org/"),
    ("oscar", "https://oscar.grycap.net/"),
    ("galaxy_tosca", "https://galaxyproject.org/"),
    ("scipion_tosca", "http://scipion.i2pc.es/"),
    ("simple_binder", "https://jupyter.org/binder/"),
    ("jupyter", "https://jupyter.org"),
    ("sciencemesh", "https://eosc.cernbox.cern.ch"),
]


class TestVREPayloadBuilder:
    """Unit tests for VREPayloadBuilder.build()."""

    @pytest.mark.parametrize("example_name,expected_vre", BUILDER_CASES)
    def test_build_package(self, example_name, expected_vre):
        package = VREPayloadBuilder.build(example_crate(example_name))
        assert package.vre_type == expected_vre

    def test_build_galaxy_package_details(self):
        package = VREPayloadBuilder.build(example_crate("galaxy"))
        assert package.workflow_url is not None
        txt_files = [f for f in package.files if f.encoding_format == "text/plain"]
        assert len(txt_files) == 1
        assert txt_files[0].name == "simpletext_input"

    def test_build_oscar_package_details(self):
        package = VREPayloadBuilder.build(example_crate("oscar"))
        assert package.fdl_url is not None
        assert len(package.oscar_input_files) == 1

    def test_build_galaxy_tosca_package(self):
        package = VREPayloadBuilder.build(example_crate("galaxy_tosca"))
        rp = package.workflow.runtime_platform
        assert rp is not None
        assert rp.install_url == (
            "https://raw.githubusercontent.com/grycap/tosca/"
            "refs/heads/eosc_dc/templates/galaxy.yaml"
        )

    def test_build_scipion_tosca_package(self):
        package = VREPayloadBuilder.build(example_crate("scipion_tosca"))
        rp = package.workflow.runtime_platform
        assert rp is not None
        assert rp.install_url == (
            "https://raw.githubusercontent.com/grycap/tosca/"
            "refs/heads/eosc_beyond/templates/scipion.yaml"
        )

    def test_build_binder_package(self):
        package = VREPayloadBuilder.build(example_crate("simple_binder"))
        assert package.vre_type == "https://jupyter.org/binder/"
        assert len(package.local_files) == 1
        assert len(package.remote_files) == 0

    def test_build_jupyter_package(self):
        package = VREPayloadBuilder.build(example_crate("jupyter"))
        assert package.vre_type == "https://jupyter.org"
        assert len(package.files) == 1

    def test_build_sciencemesh_package(self):
        package = VREPayloadBuilder.build(example_crate("sciencemesh"))
        assert package.vre_type == "https://eosc.cernbox.cern.ch"
        # no #receiver entity by design — parties are read from slots
        assert package.get_entity("#receiver") is None
        assert package.input_literal_bindings() == [
            ("Shared With", "rwelande@eosc.cernbox.cern.ch")
        ]

    def test_runtime_platform_plain_url(self):
        package = VREPayloadBuilder.build(example_crate("galaxy"))
        rp = package.workflow.runtime_platform
        assert rp is not None
        assert isinstance(rp, str)
        assert rp == "https://usegalaxy.eu/"

    def test_runtime_platform_im_dict(self):
        package = VREPayloadBuilder.build(example_crate("galaxy_tosca"))
        rp = package.workflow.runtime_platform
        assert isinstance(rp, RuntimePlatform)
        assert rp.install_url == (
            "https://raw.githubusercontent.com/grycap/tosca/"
            "refs/heads/eosc_dc/templates/galaxy.yaml"
        )
