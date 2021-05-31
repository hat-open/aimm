from pathlib import Path


root = Path(__file__).parents[1]

project = 'AIMM'
copyright = '2021, Zlatan Sičanica'
author = 'Zlatan Sičanica'


with open(root / 'VERSION') as fh:
    version = fh.read()[:-1]

extensions = [
    'sphinxcontrib.programoutput',
    'sphinx.ext.autodoc',
    'sphinxcontrib.napoleon',
    'sphinx_rtd_theme'
]

html_theme = 'sphinx_rtd_theme'

html_static_path = []

autodoc_member_order = 'bysource'
