Plugins
=======

AIMM system relies on user-written plugins for implementations of machine
learning models, preprocessing and data-fetching methods. Both server and its
clients may use the plugin API. The plugins are implemented as Python modules
that are dynamically imported at some point during servers or clients runtime.
Within these modules, plugin implementators should use the decorators from the
``aimm.plugins`` module to indicate which functions and classes are entry
points to various machine learning workflow actions. They may also, through
decorator arguments, pass information to plugin callers, allowing them to
further declare semantics of some of their arguments (e.g. declare that an
argument should receive a callback function for progress notification).

Before accessing any plugins, they need to be imported and initialized. One way
to do this (other then importing them manually) is by calling the
initialization function:

.. autofunction:: aimm.plugins.initialize

Initialize configuration schema:

.. literalinclude:: ../schemas_json/plugins.yaml
   :language: yaml


.. warning:: The AIMM plugin interface does not create a sandbox environment
    when executing plugins, it is up to the implementator to make sure not to
    perform unsafe actions

Decorators
----------

.. autodecorator:: aimm.plugins.data_access
.. autodecorator:: aimm.plugins.instantiate
.. autodecorator:: aimm.plugins.fit
.. autodecorator:: aimm.plugins.predict
.. autodecorator:: aimm.plugins.serialize
.. autodecorator:: aimm.plugins.deserialize

It is common for a model type to have all of the above defined functions, for
this reason the following class and decorator are introduced:

.. autoclass:: aimm.plugins.Model
    :members:
.. autofunction:: aimm.plugins.model


Calling plugins
---------------

After implementing and loading plugins, they can be called using following
functions:

.. autofunction:: aimm.plugins.exec_data_access
.. autofunction:: aimm.plugins.exec_instantiate
.. autofunction:: aimm.plugins.exec_fit
.. autofunction:: aimm.plugins.exec_predict
.. autofunction:: aimm.plugins.exec_serialize
.. autofunction:: aimm.plugins.exec_deserialize

State callbacks have the following signature:

.. autodata:: aimm.plugins.StateCallback
