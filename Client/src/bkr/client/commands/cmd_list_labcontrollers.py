# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

"""
bkr list-labcontrollers: List Beaker lab controllers
====================================================

.. program:: bkr list-labcontrollers

Synopsis
--------

:program:`bkr list-labcontrollers` [*options*]

Description
-----------

Prints to stdout a list of all the lab controllers attached to Beaker.

Options
-------

Common :program:`bkr` options are described in the :ref:`Options 
<common-options>` section of :manpage:`bkr(1)`.

Exit status
-----------

Non-zero on error, otherwise zero.

See also
--------

:manpage:`bkr(1)`
"""


from bkr.client import BeakerCommand


class List_LabControllers(BeakerCommand):
    """list labcontrollers"""
    enabled = True
    requires_login = False

    def options(self):
        self.parser.usage = "%%prog %s" % self.normalized_name


    def run(self, *args, **kwargs):
        self.set_hub(**kwargs)
        for lab_controller in self.hub.lab_controllers():
            print lab_controller
