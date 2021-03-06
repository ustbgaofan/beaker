
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

"""
bkr list-systems: List Beaker systems
=====================================

.. program:: bkr list-systems

Synopsis
--------

| :program:`bkr list-systems` [*options*]
|       [:option:`--available` | :option:`--free` | :option:`--mine`]
|       [:option:`--type` <type>] [:option:`--status` <status>] [:option:`--group` <group>]
|       [:option:`--arch` <arch>] [:option:`--dev-vendor-id` <vendorid>]
|       [:option:`--dev-device-id` <deviceid>] [:option:`--dev-driver` <driver>]
|       [:option:`--dev-description` <description>] [:option:`--dev-sub-vendor-id` <subvendorid>]
        [:option:`--dev-sub-device-id` <subdeviceid>]

Description
-----------

Prints to stdout a list of all matching systems in Beaker.

Options
-------

.. option:: --available

   Limit to systems which would be available to be scheduled by the current 
   user. This will exclude any systems whose access controls (group membership, 
   shared setting, etc) prevent the current user from running jobs on them.

   Note that this does *not* exclude systems which are currently occupied by 
   other users. Use :option:`--free` for that.

.. option:: --free

   Like :option:`--available`, but only includes which can be scheduled *right 
   now*.

.. option:: --removed

   Limit to systems which have been marked as ``Removed``.

.. option:: --mine

   Limit to systems which are owned by the current user.

The :option:`--available`, :option:`--free`, and :option:`--mine` options are 
mutually exclusive.

.. option:: --type <type>

   Limit to systems of type <type>. Most users will want to filter for the 
   ``Machine`` type.

.. option:: --status <status>

   Limit to systems whose status is <status>, for example ``Automated``, 
   ``Manual``, or ``Broken``.

.. option:: --group <group>

   Limit to systems which are in <group>.

.. option:: --arch <arch>

   Limit to systems of arch <arch>.

.. option:: --dev-vendor-id <vendorid>

   Limit to systems which have a device with <vendorid>.

.. option:: --dev-device-id <deviceid>

   Limit to systems which have a device with <deviceid>.

.. option:: --dev-sub-vendor-id <subvendorid>

   Limit to systems which have a device with <subvendorid>.

.. option:: --dev-sub-device-id <subdeviceid>

   Limit to systems which have a device with <subdeviceid>.

.. option:: --dev-driver <driver>

   Limit to systems which have a device with <driver>.

.. option:: --dev-description <description>

   Limit to systems which have a device with <description>.

.. option:: --xml-filter <xml>

   Limit to systems which match the given XML filter criteria. Supports the 
   same criteria as inside the ``<hostRequires/>`` element in Beaker job XML.

Common :program:`bkr` options are described in the :ref:`Options 
<common-options>` section of :manpage:`bkr(1)`.

Exit status
-----------

Non-zero on error, otherwise zero.
If no systems match the given criteria this is considered to be an error, and 
the exit status will be 1.

Examples
--------

List automated systems which belong to the kernel group and are not currently 
in use::

    bkr list-systems --free --type=Machine --status=Automated --group=kernel

See also
--------

:manpage:`bkr(1)`
"""

import sys
import urllib
import urllib2
import lxml.etree
from bkr.client import BeakerCommand

class List_Systems(BeakerCommand):
    """List systems"""
    enabled = True
    search = dict()

    def parser_add_option(self, *args, **kwargs):
        """
        Our parser add option which also populates our search options
        """
        table = kwargs.pop('table')
        option = self.parser.add_option(*args, **kwargs)
        self.search[option.dest] = table
        return option

    def options(self):
        self.parser.usage = "%%prog %s [options]" % self.normalized_name
        self.parser.add_option('--available', action='store_const',
                const='available', dest='feed',
                help='Only include systems available to be used by this user')
        self.parser.add_option('--free', action='store_const',
                const='free', dest='feed',
                help='Only include systems available '
                     'to this user and not currently being used')
        self.parser.add_option('--removed', action='store_const',
                const='removed', dest='feed',
                help='Only include systems which have been removed')
        self.parser.add_option('--mine', action='store_const',
                const='mine', dest='feed',
                help='Only include systems owned by this user')
        self.parser_add_option('--type', metavar='TYPE', table='System/Type',
                help='Only include systems of TYPE')
        self.parser_add_option('--status', metavar='STATUS', table='System/Status',
                help='Only include systems with STATUS')
        self.parser_add_option('--group', metavar='GROUP', table='System/Group',
                help='Only include systems in GROUP')
        self.parser_add_option('--arch', metavar='ARCH', table='System/Arch',
                help='Only include systems with ARCH')
        self.parser_add_option('--dev-vendor-id', metavar='VENDOR-ID',
                table='Devices/Vendor_id',
                help='only include systems with a device that has VENDOR-ID')
        self.parser_add_option('--dev-device-id', metavar='DEVICE-ID',
                table='Devices/Device_id',
                help='only include systems with a device that has DEVICE-ID')
        self.parser_add_option('--dev-sub-vendor-id', metavar='SUBVENDOR-ID',
                table='Devices/Subsys_vendor_id',
                help='only include systems with a device that has SUBVENDOR-ID')
        self.parser_add_option('--dev-sub-device-id', metavar='SUBDEVICE-ID',
                table='Devices/Subsys_device_id',
                help='only include systems with a device that has SUBDEVICE-ID')
        self.parser_add_option('--dev-driver', metavar='DRIVER',
                table='Devices/Driver',
                help='only include systems with a device that has DRIVER')
        self.parser_add_option('--dev-description', metavar='DESCRIPTION',
                table='Devices/Description',
                help='only include systems with a device that has DESCRIPTION')
        self.parser.add_option('--xml-filter', metavar='XML',
                help='only include systems matching the given XML filter, '
                'as in <hostRequires/>')
        self.parser.set_defaults(feed='')

    def run(self, *args, **kwargs):
        if args:
            self.parser.error('This command does not accept any arguments')

        qs_args = [
            ('tg_format', 'atom'),
            ('list_tgp_limit', 0),
        ]
        for i, x in enumerate(self.search.iteritems()):
            if kwargs[x[0]]:
                qs_args.extend([
                    ('systemsearch-%d.table' % i, x[1]),
                    ('systemsearch-%d.operation' % i, 'is'),
                    ('systemsearch-%d.value' % i,     kwargs[x[0]])
                ])
        if 'xml_filter' in kwargs:
            qs_args.append(('xmlsearch', kwargs['xml_filter']))

        feed_url = '/%s?%s' % (kwargs['feed'], urllib.urlencode(qs_args))

        # This will log us in using XML-RPC
        self.set_hub(**kwargs)

        # Now we can steal the cookie jar to make our own HTTP requests
        urlopener = urllib2.build_opener(urllib2.HTTPCookieProcessor(
                self.hub._transport.cookiejar))
        try:
            content = urlopener.open(self.hub._hub_url + feed_url)
        except urllib2.HTTPError,e:
            sys.stderr.write(e.read())
            sys.exit(1)
        else:
            atom = lxml.etree.parse(content)
            titles = atom.xpath('/atom:feed/atom:entry/atom:title',
                                namespaces={'atom': 'http://www.w3.org/2005/Atom'})
            if not titles:
                sys.stderr.write('Nothing Matches\n')
                sys.exit(1)
            for title in titles:
                print title.text.strip()
