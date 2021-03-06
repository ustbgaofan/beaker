
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import unittest2 as unittest
from bkr.server.model import session, SystemPermission, User
from bkr.inttest import data_setup
from bkr.inttest.client import run_client, ClientError,\
    create_client_config
import bkr.client.json_compat as json
from prettytable import PrettyTable

class PolicyListTest(unittest.TestCase):

    def setUp(self):

        with session.begin():
            self.system = data_setup.create_system(shared=False)
            self.system_public = data_setup.create_system(shared=False)
            self.user1 = data_setup.create_user()
            self.user2 = data_setup.create_user()
            self.group = data_setup.create_group()
            self.system.custom_access_policy.add_rule(
                permission=SystemPermission.edit_system, user=self.user1)
            self.system.custom_access_policy.add_rule(
                permission=SystemPermission.control_system, user=self.user2)
            self.system.custom_access_policy.add_rule(
                permission=SystemPermission.control_system, group=self.group)
            self.system_public.custom_access_policy.add_rule(
                permission=SystemPermission.control_system, everybody=True)

    def gen_expected_pretty_table(self, rows):
        table = PrettyTable(['Permission', 'User', 'Group', 'Everybody'])
        for row in rows:
            table.add_row(row)
        return table.get_string()

    def test_list_policy(self):

        # print the policies as a list
        out = run_client(['bkr', 'policy-list', self.system.fqdn])
        expected_output = self.gen_expected_pretty_table(
            (['control_system', 'X', self.group.group_name, 'No'],
             ['control_system', self.user2.user_name, 'X', 'No'],
             ['edit_system', self.user1.user_name, 'X', 'No'],
             ['view', 'X', 'X', 'Yes'])) + '\n'
        self.assertEquals(out, expected_output)

        # For the second system
        out = run_client(['bkr', 'policy-list', self.system_public.fqdn,
                          '--format','tabular'])
        expected_output = self.gen_expected_pretty_table(
            (['control_system', 'X', 'X', 'Yes'],
             ['view', 'X', 'X', 'Yes'])) + '\n'

        self.assertEquals(out, expected_output)

        # print the policies as JSON object
        out = run_client(['bkr', 'policy-list', self.system.fqdn,
                          '--format','json'])
        out = json.loads(out)
        self.assertEquals(len(out['rules']), 4)

    def test_list_policy_non_existent_system(self):

        try:
            out = run_client(['bkr', 'policy-list', 'ineverexisted'])
            self.fail('Must fail or die')
        except ClientError as e:
            self.assertIn('System not found', e.stderr_output)

    def test_list_policy_filter_mine(self):

        with session.begin():
            self.system.custom_access_policy.add_rule(
                permission=SystemPermission.edit_system, user=\
                    User.by_user_name(data_setup.ADMIN_USER))

        out = run_client(['bkr', 'policy-list',
                          '--mine', self.system.fqdn])
        expected_output = self.gen_expected_pretty_table(
            (['edit_system', 'admin', 'X', 'No'], )) + '\n'
        self.assertEquals(out, expected_output)

    def test_list_policy_filter_user(self):

        out = run_client(['bkr', 'policy-list',
                          '--user', self.user1.user_name,
                          '--user', self.user2.user_name,
                          self.system.fqdn])
        expected_output = self.gen_expected_pretty_table(
            (['control_system', self.user2.user_name, 'X', 'No'],
             ['edit_system', self.user1.user_name, 'X', 'No'])) + '\n'
        self.assertEquals(out, expected_output)

    def test_list_policy_filter_group(self):

        with session.begin():
            group = data_setup.create_group()
            self.system.custom_access_policy.add_rule(
                permission=SystemPermission.edit_system, group=group)
        out = run_client(['bkr', 'policy-list',
                          '--group', self.group.group_name,
                          '--group', group.group_name,
                          self.system.fqdn])
        expected_output = self.gen_expected_pretty_table(
            (['control_system', 'X', self.group.group_name, 'No'],
             ['edit_system', 'X', group.group_name, 'No'])) + '\n'
        self.assertEquals(out, expected_output)

    def test_list_policy_filter_multiple(self):
        try:
            run_client(['bkr', 'policy-list',
                        '--mine', 
                        '--group', self.group.group_name,
                        self.system.fqdn])
            self.fail('Must fail or die')
        except ClientError as e:
            self.assertIn('Only one filtering criteria allowed',
                          e.stderr_output)
