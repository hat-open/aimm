Backend
=======

The function of backend instances is performing model persistance. They provide
functions that allow its callers to store and retrieve modules.

The backend configuration is one of the properties in the server configuration.
Schema does not set limits on which backend implementations are available and
instead offers an interface that allows dynamic imports of backend
implementations, requiring only a ``module`` parameter that is a Python module
name of the concrete backend implementation. The exact minimal schema is as
follows:

.. literalinclude:: ../../schemas_json/server/backend/main.yaml
    :language: yaml

All backend implementations need to implement the following interface:

.. autoclass:: aimm.server.common.Backend
    :members:
.. autofunction:: aimm.server.common.create_backend
.. autofunction:: aimm.server.common.create_backend_subscription

Only one instance of a backend can be configured on a aimm server and its
configuration depends on the concrete implementation of the interface. Two
kinds of backend implementations are available with the aimm package - sqlite
and event backend.

SQLite
------

SQLite backend stores all the models into a SQLite database. The configuration
needs to follow the schema:

.. literalinclude:: ../../schemas_json/server/backend/sqlite.yaml
    :language: yaml

Only configuration property is ``path`` - path to the SQLite file where data is
stored.

Event
-----

The event backend makes use of Hat's event infrastructure to create and access
events that contain model blobs. It requires a connection to hat event server
to be configured and its configuration needs to follow the schema:

.. literalinclude:: ../../schemas_json/server/backend/event.yaml
    :language: yaml

The only configurable property, ``model_prefix`` is the prefix of the model
blob event's types. The events that the model raises will have the following
structure:

  * event type: ``[<model_prefix>, <instance_id>]``
  * source timestamp: None
  * payload: dictionary that follows the schema:

    .. code-block:: yaml

        ---
        type: object
        required:
            - type
            - instance
        properties:
            type:
                type: string
                description: |
                    model type, used to pair with deserialization function,
                    when needed
            instance:
                type: string
                description: base64 encoded serialized instance
        ...
