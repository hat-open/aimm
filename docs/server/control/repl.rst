REPL
====

REPL control serves as an interface to the REPL client. Its configuration has
the following schema:

.. literalinclude:: ../../../schemas_json/server/control/repl.yaml
    :language: yaml

REPL control works as a Websocket server, using the hat-juggler protocol. It
translates engine's state into JSON serializable data and transfers it to its
clients over local-remote data synchronization. The clients may also send
messages, which cause the server to call engine's functions and report their
results.

The server listens at the address ``ws://<host>:<port>/ws``, where ``host`` and
``port`` are configuration parameters. After connecting, the clients send and
receive messages, causing the server to execute calls to the engine's
functions. First message must be sent by the client and needs to have the
following structure:

.. code-block:: yaml

    ---
    type: object
    required:
        - type
        - data
    properties:
        type:
            const: login
        data:
            type: object
            required:
                - username
                - password
    ...

REPL control will then try to authenticate the given login data. If the
authentication fails, the connection is closed, otherwise the following JSON
message is sent to the client: ``{"type": "login_success"}``. Afterwards,
different kinds of messages may be exchanged between the control and its
clients may be exchanged.

.. note:: Login procedure here is added pro forma and might not provide optimal
   level of security for some use cases. If this is the case, it is advised to
   develop a separate control that implements a more appropriate procedure.

State
-----

Engine's state is translated into JSON with the following schema:

.. code-block:: yaml

    ---
    type: object
    required:
        - actions
        - models
    properties:
        actions:
            type: object
            patternProperties:
                "(.)+":
                    type: object
                    description: copied directly from engine's state property
        models:
            type: object
            patternProperties:
                "(.)+":
                    type: object
                    required:
                        - type
                        - id
                        - instance
                    properties:
                        type:
                            type: string
                        id:
                            type: integer
                        instance:
                            type: string
                            description: base64 encoded instance
    ...

Messages
--------

REPL control receives and sends juggler messages to its clients. Messages from
clients represent requests that correspond engine's interface, and messages in
the opposite direction are responses containing results. All messages have the
following outer structure:

.. code-block:: yaml

    ---
    type: object
    required:
        - type
        - data
    properties:
        type:
            enum:
                - create_instance
                - add_instance
                - update_instance
                - fit
                - predict
        data:
            type: object
            description: type-specific
    ...


Argument preprocessing
''''''''''''''''''''''

Messages correspond to engine's interface, and that interface provides support
for passing :class:`aimm.server.common.DataAccess` objects, to signify that an
engine action needs to execute a data access plugin before calling the main
action. Control allows sections of messages that contain arguments to take a
specific structure that signify that that argument needs to be converted into
an object. Conversion to :class:`aimm.server.common.DataAccess`,
:class:`numpy.array` and :class:`pandas.DataFrame` is currently supported. The
structure:

.. code-block:: yaml

    ---
    id: '#object_arg'
    oneOf:
      - {}
      - description: converts to common.DataAccess
        required:
            - name
            - args
            - kwargs
        properties:
            type:
                const: data_access
            name:
                type: string
                description: data access plugin name
            args:
                type: array
                items:
                    '$ref': '#object_arg'
            kwargs:
                patternProperties:
                    '(.)+':
                        '$ref': '#object_arg'
      - description: converts to numpy.array
        required:
            - data
            - dtype
        properties:
            type:
                const: numpy_array
            data:
                type: array
            dtype:
                type: string
      - description: converts to pandas.DataFrame
        required:
            - data
        properties:
            type:
                const: pandas_dataframe
            data:
                type: object
                descirption: result of pandas.DataFrame.to_dict function
      - description: converts to pandas.Series
        required:
            - data
        properties:
            type:
                const: pandas_series
            data:
                type: object
                descirption: result of pandas.Series.tolist function
    ...

Data structures, depending on their ``type``, are described hereafter.

``result``
''''''''''

Since ``create_instance``, ``add_instance``, ``update_instance`` and ``fit``
all revolve around creation or alteration of model instances they have the same
response structure:

.. code-block:: yaml

    ---
    type: object
    required:
        - type
        - success
    properties:
        type:
            const: result
        success:
            type: boolean
        model:
            type: object
            required:
                - model_type
                - instance_id
                - instance
            properties:
                model_type:
                    type: string
                instance_id:
                    type: integer
                instance:
                    type: string
                    description: base64 serialized instance
        exception:
            type: string
        traceback:
            type: array
            items:
                type: string
    ...

``create_instance``
'''''''''''''''''''

Request:

.. code-block:: yaml

    ---
    type: object
    required:
        - model_type
        - args
        - kwargs
    properties:
        model_type:
            type: string
        args:
            type: array
            items:
                '$ref': '#object_arg'
        kwargs:
            patternProperties:
                "(.)+":
                    '$ref': '#object_arg'
    ...

``add_instance``
''''''''''''''''

Request:

.. code-block:: yaml

    ---
    required:
        - model_type
        - instance
    properties:
        model_type:
            type: string
        instance:
            type: string
            description: base64 serialized instance
    ...

``update_instance``
'''''''''''''''''''

Request:

.. code-block:: yaml

    ---
    type: object
    required:
        - model_type
        - instance_id
        - instance
    properties:
        model_type:
            type: string
        instance_id:
            type: integer
        instance:
            type: string
            description: base64 serialized instance
    ...

``fit``
'''''''

Request:

.. code-block:: yaml

    ---
    type: object
    required:
        - instance_id
        - args
        - kwargs
    properties:
        instance_id:
            type: integer
        args:
            type: array
            items:
                '$ref': '#object_arg'
        kwargs:
            patternProperties:
                '(.)+':
                    '$ref': '#object_arg'
    ...

``predict``
'''''''''''

Request:

.. code-block:: yaml

    ---
    type: object
    required:
        - instance_id
        - args
        - kwargs
    properties:
        instance_id:
            type: integer
        args:
            type: array
            items:
                '$ref': '#object_arg'
        kwargs:
            patternProperties:
                '(.)+':
                    '$ref': '#object_arg'
    ...

Response:

.. code-block:: yaml

    ---
    type: object
    required:
        - type
        - success
        - result
    properties:
        type:
            const: result
        success:
            type: boolean
        result:
            oneOf:
              - {}
              - type: object
                required:
                    - type
                    - data
                properties:
                    type:
                        enum:
                            - numpy_array
                            - pandas_dataframe
                            - pandas_series
                    data:
                        type: object
                        description: |
                            prediction result serialized as json, for numpy
                            arrays and pandas Series, tolist methods are used
                            and for dataframe, its to_dict method is used
        exception:
            type: string
        traceback:
            type: array
            items:
                type: string
    ...
