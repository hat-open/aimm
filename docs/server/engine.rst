Engine
======

Engine is the central component of the AIMM system. Its purpose is handling
manageable calls to plugins, using the backend when persistence is required and
serving its state to all controllers.

Engine's part of the configuration needs to satisfy the following schema:

.. literalinclude:: ../../schemas_json/server/engine.yaml
   :language: yaml

When engine is started, it queries its backend to access all existing model
instances. The instances are then stored in engine's state. Any component
holding a reference to the engine may use it to perform different actions, such
as creating model instances, fitting them or using them for predictions. When a
new model instance is created, or an old one is updated, state change is
notified to any components that have subscribed to state changes. Additionally,
calls to the plugins themselves are manageable and engine keeps theirs states
in its state as well.

Workflow actions such as fitting or using models are ran asynchronously in
separate asyncio tasks. Additionally, any plugin they call is ran in a separate
process, wrapped in a handler that allows subscriptions to call's state (if the
plugin call supports state notification). The calls can also be cancelled,
which is done using signals - initially SIGTERM and later SIGKILL if a
configured timeout expires. Also, to avoid fork bombs, a separate pseudo-pool
is implemented to serve as an interface for process creation, disallowing
creation of new processes if a certain number of subprocesses is already
running.

Engine configuration reflects the multiprocessing nature of the implementation,
since all of the options refer to different timeouts and limitations:

  * ``sigterm_timeout`` is the number of seconds waited after SIGTERM was sent
    to a process before SIGKILL is sent if it doesn't terminate
  * ``max_children`` is the maximum amount of children - concurrent subprocesses
    that can run at the same time
  * ``check_children_period`` - the check for children counts is done
    periodically and this setting indicates how often it is checked

Engine module provides the following interface:

.. autoclass:: aimm.server.common.Engine
    :members:

.. autoclass:: aimm.server.common.Action
    :members:

Since there are no strict limitations on the arguments that may be passed to
plugins, i.e., positional and keyword arguments are mostly passed as-is,
callers of the actions have the options of passing different special kinds of
objects as arguments. These objects are interpreted by the engine as subactions
that need to be executed before the main action. E.g., a fitting function may
expect a dataset as an input, and while it is possible to pass the dataset
directly to engine's :meth:`Engine.fit` call, the caller could create a
:class:`aimm.server.common.DataAccess` object and pass it instead. This would
indicate to the engine that it needs to use the data access plugin to access
the required data before fitting. All subactions are also ran in a separate
subprocesses and notify their progress through state.

State
-----

State is a dictionary consisting of two properties, ``models`` and ``actions``.
Models are a dictionary with instance IDs as keys and
:class:`aimm.server.common.Model` instances as values. Actions are also a
dictionary, with the following structure:

.. code-block:: yaml

    ---
    description: keys are action IDs
    patternProperties:
        '(.)+':
            oneOf:
              - type: 'null'
                description: prior to start of the action call
              - type: object
                required:
                    - meta
                    - progress
                properties:
                    meta:
                        type: object
                        required:
                            - call
                        properties:
                            call:
                                type: string
                                description: call that the action is making 
                            model_type:
                                type: string
                            model:
                                type: integer
                            args:
                                type: array
                            kwargs:
                                type: object
                    progress:
                        enum:
                            - accessing_data
                            - executing
                            - complete
                    data_access:
                        type: object
                        description: |
                            keys represent argument IDs (numbers for
                            positional, strings for named), values are set by
                            plugin's state callbacks
                    action:
                        description: set by plugin state callback
    ...

Multiprocessing
---------------

The details of the multiprocessing implementation are placed in a separate
module, ``aimm.server.mprocess``. This module is in charge of providing an
interface for managed process calls. The central class of the module is the
:class:`aimm.server.mprocess.ProcessManager`. Its purpose is similar to one of
a standard :class:`multiprocessing.Pool`, main difference being that it does
not keep an exact amount of process workers alive at all times and instead
holds an :class:`asyncio.Condition` that prevents creation of new processes
until the number of children is under the ``max_children`` configuration
parameter.

The manager is implemented in the following class:

.. autoclass:: aimm.server.mprocess.ProcessManager
    :members:

The process calls are wrapped in a :class:`aimm.server.mprocess.ProcessHandler`
instance, whose interface allows callers to terminate the process call. It also
allows callers to pass their state change callback functions which are called
whenever the process' state changes.

After calling :meth:`aimm.server.mprocess.ProcessManager.create_handler` and
receiving a process handler, the call can be made using the
:meth:`aimm.server.mprocess.ProcessHandler.run` function, which, in reality,
first spawns an asyncio task that blocks until the process manager allows
creation of a new process and only then actually creates a new process.

The state notification is done using callbacks and multiprocessing pipes.
Process handler receives a ``state_cb`` argument in its constructor and this is
the function used to notify states to the rest of the system. It also provides
a method ``proc_notify_state_change``, which is a callback passed to the
function running in the separate process. This function uses a
:class:`multiprocessing.Pipe` object to send function's state values (need to
be pickle-able). Handlers also have internal state listening loops, running in
the main asyncio event loop, that react to receiving these state changes and
notify the rest of the system using the ``state_cb`` passed in the constructor.
Result of the separated process call is also passed through a separate pipe and
set as the result of the :data:`aimm.server.mprocess.ProcessHandler.result`
property.

The complete class docstring:

.. autoclass:: aimm.server.mprocess.ProcessHandler
    :members:
    :noindex:
