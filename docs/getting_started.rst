Getting started
===============

After :doc:`installing AIMM </introduction>`, its CLI and libraries become
available. Since the main purpose of the server is providing an API to
dynamically defined plugins, the first step is defining the plugins the server
will provide an interface for. The following code shows an example of a module
containing multiple plugin definitions:

.. literalinclude:: ../examples/0001/plugins/sklearn.py

The plugins defined are:

    * data access for Iris dataset inputs and outputs
    * model implementation that is actually a wrapper around sklearn's SVC

For more information on the plugin interface, consult the :doc:`documentation
entry </plugins>`.

The next step is server configuration. This involves writing a YAML file
containing the necessary settings. An example of such a configuration,
following up to the previous example, may be:

.. literalinclude:: ../examples/0001/aimm.yaml
    :language: yaml

For more details on configuring and running the server, consult the
:doc:`documentation entry </server/index>`.

Running the server now starts a service that listens on the address
``127.0.0.1:9999`` and allows clients to connect, create, fit and use SVC
models. Since the only configured control is REPL control, it should be
possible to connect using the :doc:`REPL client <clients/repl>`. Following
snippet shows how the library may be used:

.. code-block:: python

    from aimm.client import repl

    async def run():
        aimm = repl.AIMM()
        await aimm.connect('ws://127.0.0.1:9999/ws')
        m = await aimm.create_instance('plugins.sklearn.SVC')

        await m.fit(repl.DataAccessArg('iris_inputs'), repl.DataAccessArg('iris_outputs'))
        await m.predict(repl.DataAccessArg('iris_inputs'))

The code would connect to the server, create an SVC instance, remotely fit it
with Iris data and use it to perform classification.

Example of Hat integration is available in the `examples directory
<https://github.com/hat-open/aimm/tree/master/examples/0002>`_.
