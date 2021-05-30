from pathlib import Path

import aimm.version


root = Path(__file__).parents[1]

project = 'AIMM'
copyright = '2021, Zlatan Sičanica'
author = 'Zlatan Sičanica'

version = aimm.version.get_version()


extensions = [
    'sphinxcontrib.programoutput',
    'sphinxcontrib.drawio',
    'sphinx.ext.autodoc',
    'sphinxcontrib.napoleon',
    'sphinx_rtd_theme'
]

html_theme = 'sphinx_rtd_theme'

html_static_path = []

autodoc_member_order = 'bysource'
drawio_default_transparency = True
