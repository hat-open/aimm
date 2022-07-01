Iris
====

This example contains a minimal implementation of the standard iris classifier,
hosted on an AIMM server. Plugins directory contains a single plugin
implementation, one that serves as a wrapper around existing sklearn Support
Vector Classifier (SVC) implementation. To run this example, install the
requirements, add this directory to the PYTHONPATH environment variable and
call::

    aimm-server --conf aimm.yaml

While the server is running, start a jupyter notebook process and host the
``Iris.ipynb`` notebook. The notebook shows examples of how AIMM service can be
used to run plugins.

When prompted for login, the username is ``user`` and password is an empty
string.
