"""Constant data for VRE types: programming-language mappings plus the
offline fallback maps used by the registry-based resolution in
``registry.py`` when no registry entry/wins apply. No logic lives here.
"""

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
    "jupyter": "https://notebooks.egi.eu/",
    "oscar": "https://oscar.vre.eosc-data-commons.eu/",
    "vip": "https://vip.creatis.insa-lyon.fr/",
    "scipion": "http://scipion.i2pc.es/",
    "mddash": "https://mddash.cerit-sc.cz/",
    "sciencemesh": "https://eosc.cernbox.cern.ch",
    "rrp": "https://rrp-eosc.ethz.ch/",
}
