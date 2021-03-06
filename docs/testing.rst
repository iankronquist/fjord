.. _tests-chapter:

================
Testing in Fjord
================

Tests in Fjord allow us to make changes and be reasonably sure that
the system continues to work. Further, they make it easier to verify
correctness for behavioral details.


Running tests
=============

Running tests and arguments
---------------------------

To run the test suite, do::

    ./manage.py test


However, that doesn't provide the most sensible defaults. Amongst
other things, you see tons and tons and tons and tons and tons and
tons and tons and tons and tons and tons and tons and tons and tons of
debugging output. Ew.

I suggest you run it this way::

    ./manage.py test -s --noinput --logging-clear-handlers


The ``-s`` flag is important if you want to be able to drop into PDB
from within tests.

Some other helpful flags are:

``-x``:
  Fast fail. Exit immediately on failure. No need to run the whole
  test suite if you already know something is broken.

``--pdb``:
  Drop into PDB on an uncaught exception. (These show up as ``E`` or
  errors in the test results, not ``F`` or failures.)

``--pdb-fail``:
  Drop into PDB on a test failure. This usually drops you right at the
  assertion.


The test suite will create a new database named ``test_%s`` where
``%s`` is whatever value you have for
``settings.DATABASES['default']['NAME']``.

When the schema changes, you may need to drop the test database. You
can also run the test suite with ``FORCE_DB`` once to cause Django to
drop and recreate it::

    FORCE_DB=1 ./manage.py test -s --noinput --logging-clear-handlers


Running specific tests
----------------------

You can run part of the test suite by specifying the directories of the
code you want to run, like::

    ./manage.py test fjord/feedback/tests

You can specify specific tests::

    ./manage.py test fjord.feedback.tests.test_ui:TestFeedback.test_happy_url

See the output of ``./manage.py test --help`` for more arguments.


Writing New Tests
=================

Code should be written so it can be tested, and then there should be
tests for it.

When adding code to an app, tests should be added in that app that
cover the new functionality. All apps have a ``tests`` module where
tests should go. They will be discovered automatically by the test
runner as long as the look like a test.

* Avoid naming test files ``test_utils.py``, since we use a library
  with the same name. Use ``test__utils.py`` instead.

* If you're expecting ``reverse`` to return locales in the URL, use
  ``LocalizingClient`` instead of the default client for the
  ``TestCase`` class.

* We use FactoryBoy to generate model instances instead of using fixtures.
  ``fjord.feedback.tests.ResponseFactory`` generates
  ``fjord.feedback.models.Response`` instances.

* To add a smoketest, see the ``README.rst`` file in the ``smoketests/``
  directory.


Writing New JavaScript Tests
============================

We test JavaScript utility functions using `QUnit <http://qunitjs.com/>`_.

These tests are in ``fjord/base/static/tests/``.

To add a new test suite, add a couple of ``script`` lines to ``index.html`` in
the relevant place and then create a new ``test_FILENAMEHERE.js`` file
with your QUnit tests.


Changing tests
==============

Unless the current behavior, and thus the test that verifies that
behavior is correct, is demonstrably wrong, don't change tests. Tests
may be refactored as long as its clear that the result is the same.


Removing tests
==============

On those rare, wonderful occasions when we get to remove code, we
should remove the tests for it, as well.

If we liberate some functionality into a new package, the tests for
that functionality should move to that package, too.
