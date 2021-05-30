"""For various build purposes only, use pip if attempting to retrieve AIMM
version of an already installed package"""
from pathlib import Path


repo_path = Path(__file__).parents[1]


def get_version():
    with open(repo_path / 'VERSION', 'r') as fh:
        version = fh.read()[:-1]
    return version
