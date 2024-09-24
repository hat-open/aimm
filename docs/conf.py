import importlib.metadata

project = "aimm"
copyright = "2024, Zlatan Sičanica"
author = "Zlatan Sičanica"
version = "1.2.dev0"

extensions = [
    "sphinxcontrib.programoutput",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
]

html_theme = "sphinx_rtd_theme"

html_static_path = []

autodoc_member_order = "bysource"
