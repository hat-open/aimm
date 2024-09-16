from pathlib import Path
import importlib.metadata


root = Path(__file__).parents[1]

project = "AIMM"
copyright = "2024, Zlatan Sičanica"
author = "Zlatan Sičanica"
version = importlib.metadata.version(project)

extensions = [
    "sphinxcontrib.programoutput",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
]

html_theme = "sphinx_rtd_theme"

html_static_path = []

autodoc_member_order = "bysource"
