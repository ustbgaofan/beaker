bkr: Beaker client
==================

.. program:: bkr

Synopsis
--------

:program:`bkr` <subcommand> [*options*] ...

Description
-----------

Provides a scriptable command-line interface to the Beaker server.

The following subcommands are supported. Each subcommand is documented in its 
own man page. This man page is reserved for common options and features.


.. include:: subcommands.rst

.. _taskspec:

Specifying tasks
****************

Some :program:`bkr` subcommands accept one or more <taskspec> arguments. 
This allows the user to identify a job, or any subcomponent of a job, by its 
id. The format is <type>:<id> where <type> is one of the following 
abbreviations, in descending hierarchical order:

    J
        job
    RS
        recipe set
    R
        recipe
    T
        recipe-task

For example, J:123 might contain RS:456, which might contain R:789, which might 
contain T:1234 and T:5678.

This format is also used in the Beaker web UI to identify jobs and their 
subcomponents.

Options
-------

.. _common-options:

Common options
**************

These options are applicable to all :program:`bkr` subcommands.

.. option:: --hub <url>

   Connect to the Beaker server at the given URL. This overrides the 
   ``HUB_URL`` setting from the configuration file. The URL should not include 
   a trailing slash.

.. option:: --username <username>

   Authenticate using password authentication, with <username>. If a password 
   is not given using :option:`--password`, the user is prompted for the 
   password on stdin.

   This option overrides the authentication type specified in the configuration 
   file, forcing password authentication to be used.

.. option:: --password <password>

   Authenticate using <password>. This option is only applicable when 
   :option:`--username` is also passed.

.. _workflow-options:

Workflow options
****************

These options are applicable to :program:`bkr` workflow subcommands, such as 
:program:`bkr workflow-simple`.

.. option:: --dry-run, --dryrun

   Don't submit the job(s) to Beaker.

.. option:: --debug

   Print the generated job XML before submitting it to Beaker.

.. option:: --pretty-xml, --prettyxml

   Pretty-print the generated job XML in a human-readable form (with 
   indentation and line breaks).

.. option:: --wait

   Watch the newly submitted job(s) for state changes and print them to stdout. 
   The command will not exit until all submitted jobs have finished. See 
   :manpage:`bkr-job-watch(1)`.

.. option:: --no-wait, --nowait

   Do not wait on job completion [default].

.. option:: --quiet

   Be quiet, don't print warnings.

Options for selecting distro tree(s):

.. option:: --family <family>

   Run the job with the latest distro in <family> (for example: ``RedHatEnterpriseLinux6``).

.. option:: --tag <tag>

   Run the job with the latest distro tagged with <tag>. Combine this with 
   :option:`--family`. By default the ``STABLE`` tag is used.

.. option:: --distro <name>

   Run the job with distro named <name>.

.. option:: --variant <variant>

   Run the job with distro variant <variant>, for example ``Server``. Combine 
   this with :option:`--family`.

.. option:: --arch <arch> 

   Use only <arch> in job. By default, a recipe set is generated for
   each arch supported by the selected distro. This option may be
   specified multiple times. 

Options for selecting system(s):

.. option:: --machine <fqdn>

   Run the job on system with <fqdn>. This option will always select a single 
   system, and so does not make sense combined with any other system options.

.. option:: --systype <type>

   Run the job on system(s) of type <type>. This defaults to ``Machine`` which 
   is almost always what you want. Other supported values are
   ``Laptop``, ``Prototype`` and ``Resource``. ``Laptop`` type would be
   used to select a system from the available laptop
   computers. Similarly, ``Resource`` and ``Prototype`` would be used in cases
   where you would want to schedule your job against a system whose
   type has been set as such.

.. option:: --hostrequire "<tag> <operator> <value>"

   Additional <hostRequires/> for job (example: ``labcontroller=lab.example.com``).

.. option:: --keyvalue "<name> <operator> <value>"

   Run the job on system(s) which have the key <name> set to <value>
   (for example: ``NETWORK=e1000``). 

.. option:: --random

   Select a system at random. The systems owned by the user are first
   checked for availability, followed by the systems owned by the
   user's group and finally all other systems.

Options for selecting tasks:

.. option:: --task <task>

   Include <task> in the job. This option may be specified multiple times.

.. option:: --package <package>

   Include tests for <package> in the job. This option may be specified 
   multiple times.

.. option:: --task-type <type>

   Include tasks of type <type> in the job. This option may be specified 
   multiple times.

.. option:: --install <package>

   Install additional package <package> after provisioning. This uses the 
   ``/distribution/pkginstall`` task. This option may be specified
   multiple times.

.. option:: --kdump

   Enable ``kdump`` using using ``/kernel/networking/kdump``.

.. option:: --ndump

   Enable ``ndnc`` using using ``/kernel/networking/ndnc``.

.. option:: --suppress-install-task

   Omit ``/distribution/install`` which is included by default.

Options for job configuration:

.. option:: --job-group <group>

   Associate the job with <group>. This will allow other group members to 
   modify the job.

.. option:: --whiteboard <whiteboard>

   Set the job's whiteboard to <whiteboard>.

.. option:: --taskparam <name>=<value>

   Sets parameter <name> to <value> for all tasks in the job.

.. option:: --repo <url>

   Make the yum repository at <url> available during initial installation of
   the system and afterwards. This option may be specified multiple times.
   The installation may fail if the repo is not actually available.

.. option:: --repo-post <url>

   Make the yum repository at <url> available AFTER the installation. This 
   option may be specified multiple times. The repo config will be appended to
   the kickstart's %post section. Whether or not the installation succeeds is
   not affected by the availability of the repo.

   .. versionadded:: 0.14.3

.. option:: --ignore-panic 

   Disable kernel panic detection and install failure detection for the recipe. 
   By default if a kernel panic appears on the serial console, or a fatal 
   installer error appears during installation, the recipe is aborted. When 
   this option is given, the messages are ignored and the recipe is not 
   aborted.

.. option:: --cc <email>

   Add <email> to the cc list for the job(s). The cc list will receive the job 
   completion notification. This option may be specified multiple times.

.. option:: --priority <priority>

   Set job priority to <priority>. Can be ``Low``, ``Medium``, ``Normal``, 
   ``High``, or ``Urgent``. The default is ``Normal``.

.. option:: --retention-tag <tag>
 
   Specify data retention policy for this job [default: Scratch]

.. option:: --product <product>

   Associate job with <product> for data retention purposes.

Options for installation:

.. option:: --method <method>

   Installation source method (nfs, http, ftp) [default: nfs].
 
.. option:: --ks-meta <options>

   Pass kickstart metadata <options> when generating kickstart.

.. option:: --kernel-options <opts>

   Pass additional kernel options for during installation. The options string
   is applied on top of any install-time kernel options which are set by 
   default for the chosen system and distro.

.. option:: --kernel-options-post <opts>

   Pass additional kernel options for after installation. The options string is 
   applied on top of any post-install kernel options which are set by default 
   for the chosen system and distro.

Options for multi-host testing:

.. option:: --clients <number>

   Use <number> clients in the job.

.. option:: --servers <number>

   Use <number> servers in the job.

Files
-----

On startup :program:`bkr` searches the following locations in order for its config:

    :file:`~/.beaker_client/config`

    :file:`/etc/beaker/client.conf`

Environment
-----------

The following environment variables affect the operation of :program:`bkr`.

.. envvar:: BEAKER_CLIENT_CONF

   If set to a non-empty value, this overrides the usual configuration search 
   paths. This must be the full path to the configuration file.
