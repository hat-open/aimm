Hat integration
===============

This example shows the way AIMM server can be integrated into `Hat
infrastructure <https://core.hat-open.com/>`_. The example contains a minimal
SCADA-like interface that connects to a simulated power grid. The measurements
from the power grid are displayed in the GUI available at address
``localhost:23023``. If the AIMM server is ran, new information is available in
the GUI, showing estimated measurements derived from the ones that are
available, solving the problem of state estimation.

To run, first install the requirements from ``requirements.txt`` and add the
``src_py`` directory to the PYTHONPATH environment variable. Then, run the
simulation script, ``./src_py/simulation.py``. Next step is running the Hat
SCADA, which can be done using the ``./hat.sh`` script. The GUI should now be
available at ``localhost:23023``. Lastly, run the AIMM server by running the
``./aimm.sh`` script. After running the AIMM server, its estimations will also
be visible in the GUI.

When prompted for login, the username is ``user`` and the password is ``pass``.
