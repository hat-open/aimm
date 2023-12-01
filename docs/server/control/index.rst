Control
=======

Control interface is used to communicate to external actors and call engine's
functions. They may notify their respective actors of state changes and serve
as a general entry point for any external client.

Control configuration is one of the properties in the server configuration.
Similar to backend, control interface works on the principle of dynamic
imports, configuration schema only consisting of a list of objects (multiple
controls may run in parallel) that require a ``module`` parameter, which is a
Python module name that contains the concrete control implementation. The exact
configuration schema looks as follows:

.. literalinclude:: ../../../schemas_json/server/control/main.yaml
    :language: yaml

All control implementations should implement the following interface:

.. autoclass:: aimm.server.common.Control
    :members:
.. autofunction:: aimm.server.common.create_control
.. autofunction:: aimm.server.common.create_control_subscription

.. toctree::
    :maxdepth: 1

    repl
    event
