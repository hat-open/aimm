import os
from pathlib import Path
import setuptools


repo_root = Path(__file__).parent
os.chdir(repo_root)


with open(repo_root / "VERSION", "r") as fh:
    version = fh.read()[:-1]

with open(repo_root / "README.rst", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="AIMM",
    packages=setuptools.find_packages(repo_root),
    version=version,
    url="https://github.com/hat-open/aimm",
    author="Zlatan Sičanica",
    author_email="zlatan.sicanica@koncar.hr",
    description="Artificial intelligence model manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: Unix",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
    entry_points={"console_scripts": ["aimm-server = aimm.server.main:main"]},
    package_data={"": ["json_schema_repo.json"]},
    include_package_data=True,
    install_requires=[
        "appdirs>=1.4.4,<1.5",
        "hat-aio>=0.7.10,<0.8",
        "hat-json>=0.5.28,<0.6",
        "hat-monitor>=0.8.10,<0.9",
        "hat-event>=0.9.9,<0.10",
        "psutil>=6.0.0,<6.1",
    ],
)
