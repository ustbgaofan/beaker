
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

"""
.. _bkr-policy-list:

bkr policy-list: Lists access policy rules for a system
=======================================================

.. program:: bkr policy-list

Synopsis
--------

| :program:`bkr policy-list` [*options*] <fqdn>

Description
-----------

Retrieves and prints the access policy rules for a system whose FQDN is <fqdn>.

(Note: this command requires Python 2.6 or later)

Options
-------

.. option:: --mine

   Retrieves the access policy rules that have been granted directly to your user account.
   This does not include permissions granted indirectly via group permissions or the system's
   default permissions.

.. option:: --user <username>

   Retrieve the access policy rules for <username>. This option can be specified multiple times.

.. option:: --group <group>

   Retrieve the access policy rules for group, <group>. This option can be specified multiple times.

.. option:: --format tabular, --format json

   Display results in the given format. The ``tabular`` format lists one rule per
   row as a table. This is the default. The ``json`` format returns the rules as a
   JSON string and is compact.

Common :program:`bkr` options are described in the :ref:`Options
<common-options>` section of :manpage:`bkr(1)`.

Exit status
-----------

Non-zero on error, otherwise zero.

Examples
--------

List current policy list for a system::

    bkr policy-list test1.example.com

List current policy list for a system for users, user1 and user2::

    bkr policy-list --user user1 --user user2 test1.example.com

See also
--------

:manpage:`bkr(1)`, :manpage:`bkr-policy-list(1)`
"""

import urllib
import pprint
from bkr.client import BeakerCommand
import bkr.client.json_compat as json
from prettytable import PrettyTable


class Policy_List(BeakerCommand):
    """Retrieves policy list"""
    enabled = True
    requires_login = False

    def options(self):
        self.parser.usage = "%%prog %s <options> <fqdn>" % self.normalized_name
        self.parser.add_option('--mine', action="store_true", default=False,
                               help='List your access policy rules'
                               'for a system')
        self.parser.add_option('--user', metavar='USER', action="append",
                               help='List access policy rules for USER')
        self.parser.add_option('--group', metavar='GROUP', action="append",
                               help='List access policy rules for GROUP')
        self.parser.add_option('--format',
                               type='choice',
                               choices=['tabular', 'json'],
                               default='tabular',
                               help='Display results in FORMAT: '
                               'tabular, json [default: %default]')

    def run(self, *args, **kwargs):

        if len(args) != 1:
            self.parser.error('Exactly one system fqdn must be given')
        fqdn = args[0]

        rules_mine = kwargs.get('mine', None)
        rules_user = kwargs.get('user', None)
        rules_group = kwargs.get('group', None)

        # only one or none of the filtering criteria must be specified
        if len(filter(lambda x: x,
                      [rules_mine, rules_user, rules_group])) > 1:
            self.parser.error('Only one filtering criteria allowed')

        # build the query string for filtering, if any
        query_string = {}
        if rules_mine:
            query_string['mine'] = True
        elif rules_user:
            query_string['user' ] = rules_user
        elif rules_group:
            query_string['group'] = rules_group

        self.set_hub(**kwargs)
        if rules_mine:
            self.hub._login()
        requests_session = self.requests_session()
        rules_url = 'systems/%s/access-policy' % urllib.quote(fqdn, '')
        res = requests_session.get(rules_url, params=query_string)
        res.raise_for_status()

        if kwargs['format'] == 'json':
            print res.text
        else:
            policy_dict = json.loads(res.text)
            # setup table
            table = PrettyTable(['Permission', 'User', 'Group', 'Everybody'])
            for rule in policy_dict['rules']:
                everybody_humanreadble = 'Yes' if rule['everybody'] else 'No'
                table.add_row([col if col else 'X' for col in [rule['permission'],
                                                               rule['user'], rule['group'],
                                                               everybody_humanreadble]])
            print table.get_string(sortby='Permission')
