REPL
====

REPL control serves as an interface to the REPL client. Its configuration has
the following schema:

.. literalinclude:: ../../../schemas_json/server/control/repl.yaml
    :language: yaml

REPL control works as a Websocket server, using the hat-juggler protocol. It
translates engine's state into JSON serializable data and transfers it to its
clients over local-remote data synchronization. It also provides its clients an
RPC interface, which allows them to send messages causing calls to engine's
functions and receive their results.

The server listens at the address ``ws://<host>:<port>/ws``, where ``host`` and
``port`` are configuration parameters. After connecting, the clients have
access to the initial state and RPC actions.

State
-----

Before accessing the state, clients need to be authorized (described in the
Actions section). The initial state, before login is just an empty JSON object.
After successful login, engine's state is translated into JSON with the
following schema:

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

RPC interface
-------------

RPC interface provides several actions its clients may call. These actions are
documented in this section, along with some additional considerations about
result JSON representations and advanced argument passing.


Actions
"""""""

``login``
'''''''''

Authorizes the user with given username and password. Successful authorization
gives access to other actions and full state.

Arguments:
  * `username` (``str``)
  * `password` (``str``)

.. note:: Login procedure here is added pro forma and might not provide optimal
   level of security for some use cases. If this is the case, it is advised to
   develop a separate control that implements a more appropriate procedure.

``logout``
''''''''''

Logs the user out.

``create_instance``
'''''''''''''''''''

Connects to engine's ``create_instance`` method. Argument preprocessing is
supported.

Arguments:
  * `model_type` (``str``): model type as defined in plugins
  * `args` (``List[Any]``): positional arguments passed to the plugin method
  * `kwargs` (``Dict[str: Any]``): keyword arguments passed to the plugin
    method

Returns JSON representation of the model.

``add_instance``
''''''''''''''''

Connects to engine's ``add_instance`` method.

Arguments:
  * `model_type` (``str``): model type as defined in plugins
  * `instance` (``str``): base64 encoded serialized model instance

Returns JSON representation of the model.

``update_instance``
'''''''''''''''''''

Connects to engine's ``update_instance`` method.

Arguments:
  * `model_type` (``str``): model type as defined in plugins
  * `instance_id` (``int``): ID of the instance that is being updated
  * `instance` (``str``): base64 encoded serialized model instance

Returns JSON representation of the model.

``fit``
'''''''

Connects to engine's ``fit`` method. Argument preprocessing is supported.

Arguments:
  * `instance_id` (``int``): ID of the instance that is being fitted
  * `args` (``List[Any]``): positional arguments for the fitting method
  * `kwargs` (``Dict[str, Any]``): keyword arguments for the fitting method

Returns JSON representation of the model.

``predict``
'''''''''''

Connects to engine's ``predict`` method. Argument preprocessing is supported.

Arguments:
  * `instance_id` (``int``): ID of the instance that is being fitted
  * `args` (``List[Any]``): positional arguments for the fitting method
  * `kwargs` (``Dict[str, Any]``): keyword arguments for the fitting method

Returns prediction converted to JSON.

JSON representations
""""""""""""""""""""

Some data structures mentioned in the sections above are, by the default, not
JSON serializable and JSON schema of the structure they take is described in
this section.

Models schema:

.. code-block:: yaml
   
    ---
    type: object
    required:
        - instance_id
        - model_type
        - instance
    properties:
        instance_id:
            type: integer
        model_type:
            type: string
        instance:
            type: string
            description: base64 encoded serialized model instance
    ...


Prediction schema:


.. code-block:: yaml

    ---
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
    ...

Argument preprocessing
""""""""""""""""""""""

Actions correspond to engine's interface, and that interface provides support
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
