
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os
import unittest2 as unittest
import subprocess
import re
import textwrap
from threading import Thread
from turbogears.database import session
from bkr.inttest import data_setup, with_transaction
from bkr.inttest.client import run_client, start_client, \
    create_client_config, ClientError
from bkr.server.model import Job

class WorkflowSimpleTest(unittest.TestCase):

    @with_transaction
    def setUp(self):
        self.distro = data_setup.create_distro(tags=[u'STABLE'])
        self.distro_tree = data_setup.create_distro_tree(distro=self.distro)
        self.task = data_setup.create_task()

    def test_job_group(self):
        with session.begin():
            user_in_group = data_setup.create_user(password='password')
            group = data_setup.create_group()
            user_in_group.groups.append(group)
            user_not_in_group = data_setup.create_user(password='password')

        # Test submitting on behalf of user's group
        config1 = create_client_config(username=user_in_group.user_name,
            password='password')
        out = run_client(['bkr', 'workflow-simple', '--random',
                '--arch', self.distro_tree.arch.arch,
                '--family', self.distro.osversion.osmajor.osmajor,
                '--job-group', group.group_name,
                '--task', self.task.name], config=config1)
        self.assertTrue(out.startswith('Submitted:'), out)
        m = re.search('J:(\d+)', out)
        job_id = m.group(1)
        with session.begin():
            job = Job.by_id(job_id)
        self.assertEqual(group, job.group)

        # Test submitting on behalf of group user does not belong to
        config2 = create_client_config(username=user_not_in_group.user_name,
            password='password')
        try:
            out2 = run_client(['bkr', 'workflow-simple', '--random',
                    '--arch', self.distro_tree.arch.arch,
                    '--family', self.distro.osversion.osmajor.osmajor,
                    '--job-group', group.group_name,
                    '--task', self.task.name], config=config2)
            fail('should raise')
        except ClientError, e:
            self.assertTrue('User %s is not a member of group %s' % \
                (user_not_in_group.user_name, group.group_name) in \
                e.stderr_output, e)

    def test_submit_job(self):
        out = run_client(['bkr', 'workflow-simple', '--random',
                '--arch', self.distro_tree.arch.arch,
                '--family', self.distro.osversion.osmajor.osmajor,
                '--task', self.task.name])
        self.assert_(out.startswith('Submitted:'), out)

    def test_submit_job_wait(self):
        args = ['bkr', 'workflow-simple', '--random',
                '--arch', self.distro_tree.arch.arch,
                '--family', self.distro.osversion.osmajor.osmajor,
                '--task', self.task.name,
                '--wait']
        proc = start_client(args)
        out = proc.stdout.readline().rstrip()
        self.assert_(out.startswith('Submitted:'), out)
        m = re.search('J:(\d+)', out)
        job_id = m.group(1)

        out = proc.stdout.readline().rstrip()
        self.assert_('Watching tasks (this may be safely interrupted)...' == out)

        with session.begin():
            job = Job.by_id(job_id)
            job.cancel()
            job.update_status()

        returncode = proc.wait()
        self.assert_(returncode == 1)

    def test_clean_defaults(self):
        out = run_client(['bkr', 'workflow-simple',
                '--dryrun', '--prettyxml',
                '--arch', self.distro_tree.arch.arch,
                '--family', self.distro.osversion.osmajor.osmajor,
                '--task', self.task.name])
        # Try to minimise noise in the default output
        self.assertNotIn('ks_appends', out)

    def test_hostrequire(self):
        out = run_client(['bkr', 'workflow-simple',
                '--dryrun', '--prettyxml',
                '--hostrequire', 'hostlabcontroller=lab.example.com',
                '--arch', self.distro_tree.arch.arch,
                '--family', self.distro.osversion.osmajor.osmajor,
                '--task', self.task.name])
        self.assertIn('<hostlabcontroller op="=" value="lab.example.com"/>', out)

    def test_repo(self):
        first_url = 'http://repo1.example.invalid'
        second_url = 'ftp://repo2.example.invalid'
        out = run_client(['bkr', 'workflow-simple',
                '--dryrun', '--prettyxml',
                '--repo', first_url,
                '--repo', second_url,
                '--arch', self.distro_tree.arch.arch,
                '--family', self.distro.osversion.osmajor.osmajor,
                '--task', self.task.name])
        expected_snippet = '<repo name="myrepo_%(idx)s" url="%(repoloc)s"/>'
        first_repo = expected_snippet % dict(idx=0, repoloc=first_url)
        self.assertIn(first_repo, out)
        second_repo = expected_snippet % dict(idx=1, repoloc=second_url)
        self.assertIn(second_repo, out)

    # https://bugzilla.redhat.com/show_bug.cgi?id=867087
    def test_repopost(self):
        first_url = 'http://repo1.example.invalid'
        second_url = 'ftp://repo2.example.invalid'
        out = run_client(['bkr', 'workflow-simple',
                '--dryrun', '--prettyxml',
                '--repo-post', first_url,
                '--repo-post', second_url,
                '--arch', self.distro_tree.arch.arch,
                '--family', self.distro.osversion.osmajor.osmajor,
                '--task', self.task.name])
        expected_snippet = textwrap.dedent('''\
            cat << EOF >/etc/yum.repos.d/beaker-postrepo%(idx)s.repo
            [beaker-postrepo%(idx)s]
            name=beaker-postrepo%(idx)s
            baseurl=%(repoloc)s
            enabled=1
            gpgcheck=0
            skip_if_unavailable=1
            EOF
            ''')
        first_repo = expected_snippet % dict(idx=0, repoloc=first_url)
        self.assertIn(first_repo, out)
        second_repo = expected_snippet % dict(idx=1, repoloc=second_url)
        self.assertIn(second_repo, out)
        # Also check these *aren't* included as install time repos
        install_repo_url_attribute = 'url="%s"'
        self.assertNotIn(install_repo_url_attribute % first_url, out)
        self.assertNotIn(install_repo_url_attribute % second_url, out)

    # https://bugzilla.redhat.com/show_bug.cgi?id=972417
    def test_servers_default_zero(self):
        out = run_client(['bkr', 'workflow-simple', '--distro', self.distro.name,
                '--task', '/distribution/reservesys',
                '--clients', '2'])
        self.assertTrue(out.startswith('Submitted:'), out)
        m = re.search('J:(\d+)', out)
        job_id = m.group(1)
        with session.begin():
            job = Job.by_id(job_id)
            self.assertEquals(len(job.recipesets), 1)
            self.assertEquals(len(job.recipesets[0].recipes), 2)
            self.assertEquals(job.recipesets[0].recipes[0].tasks[1].role, 'CLIENTS')
            self.assertEquals(job.recipesets[0].recipes[1].tasks[1].role, 'CLIENTS')

    # https://bugzilla.redhat.com/show_bug.cgi?id=972417
    def test_clients_default_zero(self):
        out = run_client(['bkr', 'workflow-simple', '--distro', self.distro.name,
                '--task', '/distribution/reservesys',
                '--servers', '2'])
        self.assertTrue(out.startswith('Submitted:'), out)
        m = re.search('J:(\d+)', out)
        job_id = m.group(1)
        with session.begin():
            job = Job.by_id(job_id)
            self.assertEquals(len(job.recipesets), 1)
            self.assertEquals(len(job.recipesets[0].recipes), 2)
            self.assertEquals(job.recipesets[0].recipes[0].tasks[1].role, 'SERVERS')
            self.assertEquals(job.recipesets[0].recipes[1].tasks[1].role, 'SERVERS')
