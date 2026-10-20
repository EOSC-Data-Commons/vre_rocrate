"""RRP support — programming language, crate building, and the
input_dataset accessor on VREPayload.

Covers the reference RRP tool from the req-packager reference
implementation (see ``examples/rrp.py``) end-to-end: launch request →
RocrateBuilder → VREPayloadBuilder.
"""

import pytest

from vre_rocrate import (
    RRP_PROGRAMMING_LANGUAGE,
    DatasetHandle,
    DatasetReference,
    FileInput,
    LaunchInput,
    RocrateBuilder,
    SlotDefinition,
    ToolMeta,
    VRELaunchRequest,
    VREPayloadBuilder,
)
from vre_rocrate.constants import VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM

RRP_URI = (
    "https://gitlab.ethz.ch/Reproducible-Research-Platform/tools/Cell-Doubling-Time"
)
RRP_DOCKER_IMAGE = "reproducibleresearchplatform/rrp-eosc:cell-doubling-time_1.0.1"
DATASET_URL = "https://doi.org/10.5281/zenodo.20507550"
IMAGE_0_URL = "https://zenodo.org/records/20507550/files/image_0.tif"
IMAGE_1_URL = "https://zenodo.org/records/20507550/files/image_1.tif"


def _rrp_request(with_dataset=True):
    return VRELaunchRequest(
        tool=ToolMeta(
            id="::st:002",
            version="v0",
            name="Reproducible Research Platform (RRP)",
            uri=RRP_URI,
            types=["general", "rrp"],
            description="RRP as general tool",
            docker_image=RRP_DOCKER_IMAGE,
            slots=[
                SlotDefinition(
                    id="image_0.tif", name="Image 0 (TIF)", slot_type="file"
                ),
                SlotDefinition(
                    id="image_1.tif", name="Image 1 (TIF)", slot_type="file"
                ),
            ],
        ),
        input=LaunchInput(
            dataset=(
                DatasetHandle(
                    url=DATASET_URL,
                    title="Cell doubling time dataset",
                    description="Microscopy images for cell doubling time analysis",
                )
                if with_dataset
                else None
            ),
            slots={
                "Image 0 (TIF)": FileInput(
                    name="image_0.tif", url=IMAGE_0_URL, mime_type="image/tiff"
                ),
                "Image 1 (TIF)": FileInput(
                    name="image_1.tif", url=IMAGE_1_URL, mime_type="image/tiff"
                ),
            },
        ),
    )


def _entity(graph, eid):
    return next(e for e in graph if e.get("@id") == eid)


# ---------------------------------------------------------------------------
# Crate building
# ---------------------------------------------------------------------------


def test_built_crate_has_rrp_computer_language():
    graph = RocrateBuilder.build_from_launch_request(_rrp_request())["@graph"]
    lang = _entity(graph, "#rrp-lang")
    assert lang["@type"] == "ComputerLanguage"
    assert lang["identifier"] == RRP_PROGRAMMING_LANGUAGE


def test_built_crate_has_formal_parameters_for_slots():
    graph = RocrateBuilder.build_from_launch_request(_rrp_request())["@graph"]
    fp_ids = {e["@id"] for e in graph if e.get("@type") == "FormalParameter"}
    assert fp_ids == {"#input-image_0.tif", "#input-image_1.tif"}


def test_built_crate_has_dataset_entity():
    graph = RocrateBuilder.build_from_launch_request(_rrp_request())["@graph"]
    ds = _entity(graph, DATASET_URL)
    assert ds["@type"] == "Dataset"
    assert ds["name"] == "Cell doubling time dataset"


def test_builder_resolves_rrp_type_and_runtime_platform():
    builder = RocrateBuilder(_rrp_request())
    assert builder.vre_type == "rrp"
    wf = _entity(builder.build()["@graph"], RRP_URI)
    assert wf["runtimePlatform"] == VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM["rrp"]


def test_built_crate_workflow_carries_docker_image():
    graph = RocrateBuilder.build_from_launch_request(_rrp_request())["@graph"]
    wf = _entity(graph, RRP_URI)
    assert wf["dockerImage"] == RRP_DOCKER_IMAGE
    assert all(e["@id"] != "#tool-metadata" for e in graph)


# ---------------------------------------------------------------------------
# Payload — input_dataset accessor
# ---------------------------------------------------------------------------


def test_payload_input_dataset_extracted():
    crate = RocrateBuilder.build_from_launch_request(_rrp_request())
    payload = VREPayloadBuilder.build(crate)
    assert isinstance(payload.input_dataset, DatasetReference)
    assert payload.input_dataset.url == DATASET_URL
    assert payload.input_dataset.name == "Cell doubling time dataset"
    assert payload.input_dataset.description == (
        "Microscopy images for cell doubling time analysis"
    )
    assert payload.programming_language == RRP_PROGRAMMING_LANGUAGE


def test_payload_workflow_docker_image_and_url():
    crate = RocrateBuilder.build_from_launch_request(_rrp_request())
    payload = VREPayloadBuilder.build(crate)
    assert payload.workflow.url == RRP_URI
    assert payload.workflow.docker_image == RRP_DOCKER_IMAGE


def test_payload_input_dataset_none_without_dataset_entity():
    crate = RocrateBuilder.build_from_launch_request(_rrp_request(with_dataset=False))
    payload = VREPayloadBuilder.build(crate)
    assert payload.input_dataset is None
