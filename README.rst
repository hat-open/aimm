Artificial Intelligence Model Manager
=====================================

The Artificial Intelligence Model Manager (AIMM) project aims to provide
resources for management of computational intelligence models. Using a
plugin-based approach, it provides a services capable of:

  * creating and storing models
  * fitting models
  * upload of already fitted models
  * data access
  * running the models

The server also has support for changeable frontend and persistence interfaces.
This allows users to implement the ways server communicates to its clients
(multiple parallel interfaces are supported) or stores the models. There are
also default interfaces that are supported for both of these functions.

Installation
------------

AIMM is a Python (3.8 and newer) package containing implementations of the
server implementation and some of its clients. It can be installed with the
following command::

    pip install aimm

Installation using ``setup.py`` script is also possible, but only if the
development environment is set up. 

Development environment
-----------------------

Development environment includes, besides the standard requirements of the base
AIMM package, various tools and libraries that are used for the build process,
documentation and testing. To set up the development environment, Python 3.8
and pip are needed. Dependencies can be installed by calling::
    
    pip install -r requirements.txt

All other generic tasks like testing and documentation building are done
through the build tool, use ``doit list`` to preview the complete list of all
available tasks.
