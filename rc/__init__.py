"""

Top level module for LBNE Run Control prototype.

The following commands should be done in the directory above this one.

To install for local testing (e.g. in a `virtualenv`),

.. code-block:: bash

    ./setup.py develop

To generate documentation:

.. code-block:: bash

    sphinx-apidoc -F -o docs rc
    pushd docs
    DJANGO_SETTINGS_MODULE=rc.web.main.settings make html
    popd

To run unit tests:

.. code-block:: bash

    python manage.py test

"""
