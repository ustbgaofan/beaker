
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os
import unittest2 as unittest
from nose.plugins.skip import SkipTest
from turbogears.database import session
from bkr.inttest import data_setup, with_transaction, start_process, \
    stop_process, CONFIG_FILE, edit_file
from bkr.inttest.client import run_client, create_client_config, ClientError

class JobDeleteTest(unittest.TestCase):

    @with_transaction
    def setUp(self):
        self.user = data_setup.create_user(password=u'asdf')
        self.job = data_setup.create_completed_job(owner=self.user)
        self.client_config = create_client_config(username=self.user.user_name,
                password='asdf')

    def test_delete_group_job(self):
        with session.begin():
            group = data_setup.create_group()
            user = data_setup.create_user(password='password')
            user2 = data_setup.create_user()
            user.groups.append(group)
            user2.groups.append(group)
            self.job.group = group
            self.job.owner = user2
        client_config = create_client_config(username=user.user_name,
            password='password')
        out = run_client(['bkr', 'job-delete', self.job.t_id],
                config=client_config)
        self.assert_(out.startswith('Jobs deleted:'), out)
        self.assert_(self.job.t_id in out, out)

    def test_delete_job(self):
        out = run_client(['bkr', 'job-delete', self.job.t_id],
                config=self.client_config)
        self.assert_(out.startswith('Jobs deleted:'), out)
        self.assert_(self.job.t_id in out, out)

    def test_delete_others_job(self):
        with session.begin():
            other_user = data_setup.create_user(password=u'asdf')
            other_job = data_setup.create_completed_job(owner=other_user)
        try:
            out = run_client(['bkr', 'job-delete', other_job.t_id],
                             config=self.client_config)
            fail('should raise')
        except ClientError, e:
            self.assert_("don't have permission" in e.stderr_output)

    def test_cant_delete_group_mates_job(self):
        # XXX This whole test can go away with BZ#1000861
        try:
            stop_process('gunicorn')
        except ValueError:
            # It seems gunicorn is not a running process
            raise SkipTest('Can only run this test against gunicorn')
        try:
            tmp_config = edit_file(CONFIG_FILE, 'beaker.deprecated_job_group_permissions.on = True',
                'beaker.deprecated_job_group_permissions.on = False')
            start_process('gunicorn', env={'BEAKER_CONFIG_FILE': tmp_config.name})
            with session.begin():
                group = data_setup.create_group()
                mate = data_setup.create_user(password=u'asdf')
                test_job = data_setup.create_completed_job(owner=mate)
                data_setup.add_user_to_group(self.user, group)
                data_setup.add_user_to_group(mate, group)
            try:
                run_client(['bkr', 'job-delete', test_job.t_id],
                    config=self.client_config)
                self.fail('We should not have permission to delete %s' % \
                    test_job.t_id)
            except ClientError, e:
                self.assertIn("You don't have permission to delete job %s" %
                test_job.t_id, e.stderr_output)
        finally:
            stop_process('gunicorn')
            start_process('gunicorn')

    def test_delete_group_mates_job(self):
        with session.begin():
            group = data_setup.create_group()
            mate = data_setup.create_user(password=u'asdf')
            test_job = data_setup.create_completed_job(owner=mate)
            data_setup.add_user_to_group(self.user, group)
            data_setup.add_user_to_group(mate, group)
        out = run_client(['bkr', 'job-delete', test_job.t_id],
                         config=self.client_config)
        self.assert_(out.startswith('Jobs deleted:'), out)
        self.assert_(test_job.t_id in out, out)

    def test_delete_job_with_admin(self):
        with session.begin():
            other_user = data_setup.create_user(password=u'asdf')
            tag = data_setup.create_retention_tag(name=u'myblahtag')
            job1 = data_setup.create_completed_job(owner=other_user)
            job2 = data_setup.create_completed_job(owner=other_user, \
                                                   retention_tag=tag)

        # As the default admin user
        # Admin can delete other's job with job ID
        out = run_client(['bkr', 'job-delete', job1.t_id])
        self.assert_(out.startswith('Jobs deleted:'), out)
        self.assert_(job1.t_id in out, out)

        # Admin can not delete other's job with tags
        out = run_client(['bkr', 'job-delete', '-t%s' % tag.tag])
        self.assert_(out.startswith('Jobs deleted:'), out)
        self.assert_(job2.t_id not in out, out)

    # https://bugzilla.redhat.com/show_bug.cgi?id=595512
    def test_invalid_taskspec(self):
        try:
            run_client(['bkr', 'job-delete', '12345'])
            fail('should raise')
        except ClientError, e:
            self.assert_('Invalid taskspec' in e.stderr_output)
