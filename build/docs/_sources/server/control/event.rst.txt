Event
=====

Event control communicates with hat's event server and, responding to events,
calls engine's methods and reports their results over the same event bus. The
control's configuration needs to satisfy the following schema:

.. literalinclude:: ../../../schemas_json/server/control/event.yaml
    :language: yaml

State
-----

Upon any engine state change, event control registers an event with the
following structure:

  * type: ``[<state_type>]``
  * source_timestamp is None
  * payload: JSON with following schema:

    .. code-block:: yaml

        ---
        type: object
        required:
            - models
            - actions
        properties:
            models:
                type: object
                patternProperties:
                    '(.)+':
                        type: string
                        description: model type
            actions:
                type: object
                description: copied as-is from engine's state
        ...

Action requests and states
--------------------------

Engine's functions are used as reactions to received events. Control receives
events with types that match one of the ``[<prefix>, '*']`` query types and
calls the functions depending on which exact prefix has matched.

Prior to the calling the functions, arguments passed in the payload may be
preprocessed and converted into :class:`aimm.server.common.DataAccess` objects
of they have a specific structure. Arguments of any call specified in the
request event's payload should have the following structure:

.. code-block:: yaml

    ---
    id: '#object_arg'
    oneOf:
      - {}
      - description: converted to ``common.DataAccess``
        type: object
        required:
            - type
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
    ...

The control registers events that refer directly to the request that started
the action and that contain information on the actions state, and, if an action
returns it, its result. The event has the following structure:

  * type: ``[<action_state_type>]``
  * source_timestamp is None
  * payload: JSON with the following schema:

    .. code-block:: yaml

        ---
        type: object
        required:
            - request_id
            - result
        properties:
            request_id:
                type: object
                description: |
                    event id that started the execution
            status:
                enum:
                    - IN_PROGRESS
                    - DONE
                    - FAILED
                    - CANCELLED
            result: {}
        ...

Create instance
'''''''''''''''

Incoming event structure:

  * type: ``[<create_instance_prefix>, '*']``
  * payload with structure:

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
                    type: '#object_arg'
            kwargs:
                patternProperties:
                    '(.)+':
                        '$ref': '#object_arg'
        ...

Result passed in the response is either an integer, representing ID of the
generated instance, or ``None`` if creation has failed.


Add instance
''''''''''''

Incoming event structure:

  * type: ``[<add_instance_prefix>, '*']``
  * payload with structure:

    .. code-block:: yaml

        ---
        type: object
        required:
            - model_type
            - instance
        properties:
            model_type:
                type: string
            instance:
                type: string
                description: base64 encoded instance
        ...

Result passed in the response is either an integer, representing ID of the
generated instance, or ``None`` if creation has failed.

Update instance
'''''''''''''''

Incoming event structure:

  * type: ``[<update_instance_prefix>, <instance_id>, '*']``
  * payload with structure:

    .. code-block:: yaml

        ---
        type: object
        required:
            - model_type
            - instance
        properties:
            model_type:
                type: string
            instance:
                type: string
                description: base64 encoded instance
        ...

Result is a boolean, ``true`` if update was performed successfully.

Fit
'''

Incoming event structure:

  * type: ``[<fit_prefix>, <instance_id>, '*']``
  * payload with structure:

    .. code-block:: yaml

        ---
        type: object
        required:
            - args
            - kwargs
        properties:
            args:
                type: array
                items:
                    type:
                        '$ref': '#object_arg'
            kwargs:
                patternProperties:
                    '(.)+':
                        '$ref': '#object_arg'
        ...

Result is a boolean, ``true`` if update was performed successfully.

Predict
'''''''

Incoming event structure:

  * type: ``[<predixt_prefix>, <instance_id>, '*']``
  * payload with structure:

    .. code-block:: yaml

        ---
        type: object
        required:
            - args
            - kwargs
        properties:
            args:
                type: array
                items:
                    type:
                        '$ref': '#object_arg'
            kwargs:
                patternProperties:
                    '(.)+':
                        '$ref': '#object_arg'
        ...

Result is the prediction, exact value returned by the call to the predict
plugin.

Cancel
''''''

Any action that can have the state ``IN_PROGRESS`` may be canceled. This is
done by registering a cancel event, with the following structure:

  * type ``[<cancel_prefix>, '*']``
  * JSON payload that is a dictionary representation of the id of the event
    that started the action
