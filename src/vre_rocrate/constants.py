"""Constants for VRE types and programming language mappings."""

GALAXY_PROGRAMMING_LANGUAGE = "https://galaxyproject.org/"
BINDER_PROGRAMMING_LANGUAGE = "https://jupyter.org/binder/"
SCIENCEMESH_PROGRAMMING_LANGUAGE = "https://eosc.cernbox.cern.ch"
SCIPION_PROGRAMMING_LANGUAGE = "http://scipion.i2pc.es/"
OSCAR_PROGRAMMING_LANGUAGE = "https://oscar.grycap.net/"
JUPYTER_PROGRAMMING_LANGUAGE = "https://jupyter.org"
VIP_PROGRAMMING_LANGUAGE = "https://vip.creatis.insa-lyon.fr/"
MDDASH_PROGRAMMING_LANGUAGE = "https://github.com/CERIT-SC/mddash"

VRE_TYPE_TO_PROGRAMMING_LANGUAGE = {
    "galaxy": GALAXY_PROGRAMMING_LANGUAGE,
    "oscar": OSCAR_PROGRAMMING_LANGUAGE,
    "scipion": SCIPION_PROGRAMMING_LANGUAGE,
    "binder": BINDER_PROGRAMMING_LANGUAGE,
    "jupyter": JUPYTER_PROGRAMMING_LANGUAGE,
    "vip": VIP_PROGRAMMING_LANGUAGE,
    "mddash": MDDASH_PROGRAMMING_LANGUAGE,
    "sciencemesh": SCIENCEMESH_PROGRAMMING_LANGUAGE,
}

VRE_TYPE_TO_DISPLAY_NAME = {
    "galaxy": "Galaxy",
    "oscar": "OSCAR",
    "scipion": "Scipion",
    "binder": "Binder",
    "jupyter": "Jupyter Notebook",
    "vip": "VIP",
    "mddash": "MDDash",
    "sciencemesh": "Jupyter Notebook",
}

VRE_TYPE_TO_LANGUAGE_URL = {
    "galaxy": "https://galaxyproject.org/",
    "oscar": "https://oscar.grycap.net/",
    "scipion": "http://scipion.i2pc.es/",
    "binder": "https://jupyter.org/binder/",
    "jupyter": "https://jupyter.org",
    "vip": "https://vip.creatis.insa-lyon.fr/",
    "mddash": "https://github.com/CERIT-SC/mddash",
    "sciencemesh": "https://jupyter.org/",
}

VRE_TYPES = tuple(VRE_TYPE_TO_PROGRAMMING_LANGUAGE.keys())


# ------------------------------------------------------------------
# req-packager tool-type -> vre_type resolution
# ------------------------------------------------------------------

TOOL_TYPE_TO_VRE_TYPE: dict[str, str] = {
    "egi-replay": "binder",
    "binder": "binder",
    "galaxy": "galaxy",
    "galaxy_workflow": "galaxy",
    "oscar": "oscar",
    "vip": "vip",
    "boutique": "vip",
    "scipion": "scipion",
    "jupyter": "jupyter",
    "mddash": "mddash",
    "sciencemesh": "sciencemesh",
    "cernbox": "sciencemesh",
    "mybinder": "binder",
    "binder-launcher": "binder",
    "rrp": "rrp",
}

VRE_TYPE_TO_DEFAULT_RUNTIME_PLATFORM: dict[str, str] = {
    "galaxy": "https://usegalaxy.eu/",
    "binder": "https://mybinder.org/",
    "jupyter": "https://jupyterhub.egi.eu/",
    "oscar": "https://oscar.grycap.net/",
    "vip": "https://vip.creatis.insa-lyon.fr/",
    "scipion": "http://scipion.i2pc.es/",
    "mddash": "https://mddash.cerit-sc.cz/",
    "sciencemesh": "https://eosc.cernbox.cern.ch",
    "rrp": "https://rrp-eosc.ethz.ch/",
}


def resolve_vre_type(tool) -> str:
    """Resolve a vre_type from a ToolMeta via three-layer fallback."""
    if "vre_type" in tool.raw_definition:
        v = tool.raw_definition["vre_type"]
        if v in VRE_TYPES:
            return v
    for t in tool.types:
        if t in TOOL_TYPE_TO_VRE_TYPE:
            return TOOL_TYPE_TO_VRE_TYPE[t]
    for pattern, vtype in [
        ("galaxyproject.org", "galaxy"),
        ("usegalaxy.eu", "galaxy"),
        ("usegalaxy.org", "galaxy"),
        ("jupyter.org", "jupyter"),
        ("oscar.grycap", "oscar"),
        ("vip.creatis", "vip"),
        ("cernbox.cern.ch", "sciencemesh"),
        ("rrp-eosc", "rrp"),
    ]:
        if pattern in tool.uri:
            return vtype
    raise ValueError(f"Cannot resolve vre_type from tool: {tool.id}")
