#!/usr/bin/python
# vim: set fileencoding=utf-8 :

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from bkr.inttest.server.selenium import WebDriverTestCase
from bkr.inttest.server.webdriver_utils import login, logout, is_text_present
from bkr.inttest import data_setup, get_server_base, with_transaction
from bkr.inttest.assertions import assert_has_key_with_value
from bkr.server.model import Arch, System, OSMajor, SystemPermission
from turbogears.database import session
import pkg_resources
import unittest2 as unittest
from tempfile import NamedTemporaryFile
from decimal import Decimal

class CSVImportTest(WebDriverTestCase):

    def setUp(self):
        with session.begin():
            self.system = data_setup.create_system()
            self.browser = self.get_browser()

    def tearDown(self):
        self.browser.quit()

    def import_csv(self, contents):
        b = self.browser
        b.get(get_server_base() + 'csv/csv_import')
        csv_file = NamedTemporaryFile(prefix=self.__module__)
        csv_file.write(contents)
        csv_file.flush()
        b.find_element_by_name('csv_file').send_keys(csv_file.name)
        b.find_element_by_name('csv_file').submit()

    def test_system(self):
        login(self.browser)
        orig_date_modified = self.system.date_modified
        self.import_csv((u'csv_type,fqdn,location,arch\n'
                u'system,%s,Under my desk,ia64' % self.system.fqdn)
                .encode('utf8'))
        self.failUnless(is_text_present(self.browser, "No Errors"))
        with session.begin():
            session.refresh(self.system)
            self.assertEquals(self.system.location, u'Under my desk')
            self.assert_(Arch.by_name(u'ia64') in self.system.arch)
            self.assert_(self.system.date_modified > orig_date_modified)

        # attempting to import a system with no FQDN should fail
        self.import_csv((u'csv_type,fqdn,location,arch\n'
                         u'system,'',Under my desk,ia64').encode('utf8'))
        self.assertEquals(self.browser.find_element_by_xpath(
            '//table[@id="csv-import-log"]//td').text,
                          "Error importing system on line 2: "
                          "System must have an associated FQDN")

        # attempting to import a system with an invalid FQDN should fail
        self.import_csv((u'csv_type,fqdn,location,arch\n'
                         u'system,invalid--fqdn,Under my desk,ia64').encode('utf8'))
        self.assertEquals(self.browser.find_element_by_xpath(
            '//table[@id="csv-import-log"]//td').text,
                          "Error importing system on line 2: "
                          "System has an invalid FQDN: invalid--fqdn")

    #https://bugzilla.redhat.com/show_bug.cgi?id=987157
    def test_system_rename(self):
        login(self.browser)
        # attempt to rename existing system to an invalid FQDN should keep 
        # the system unmodified

        with session.begin():
            session.refresh(self.system)
        orig_date_modified = self.system.date_modified
        self.import_csv((u'csv_type,id,fqdn,location,arch\n'
                    u'system,%s,new--fqdn.name,%s,%s' % (self.system.id,
                                                         self.system.location, self.system.arch[0])).encode('utf8'))
        with session.begin():
            session.refresh(self.system)
        self.assertEquals(self.system.date_modified, orig_date_modified)
        self.assertEquals(self.browser.find_element_by_xpath(
            '//table[@id="csv-import-log"]//td').text,
                          "Error importing system on line 2: "
                          "System has an invalid FQDN: new--fqdn.name")

        # attempt to rename a non-existent system should fail
        orig_date_modified = self.system.date_modified
        non_existent_system_id = -1
        self.import_csv((u'csv_type,id,fqdn,location,arch\n'
                    u'system,%s,new--fqdn.name,%s,%s' % (non_existent_system_id,
                                                         self.system.location, self.system.arch[0])).encode('utf8'))
        with session.begin():
            session.refresh(self.system)
        self.assertEquals(self.system.date_modified, orig_date_modified)
        self.assertEquals(self.browser.find_element_by_xpath(
            '//table[@id="csv-import-log"]//td').text,
                          "Error importing system on line 2: "
                          "Non-existent system id")

        # successfully rename existing system
        orig_date_modified = self.system.date_modified
        self.import_csv((u'csv_type,id,fqdn,location,arch\n'
                    u'system,%s,new.fqdn.name,Under my desk,ia64' % self.system.id).encode('utf8'))
        with session.begin():
            session.refresh(self.system)

        self.assertGreater(self.system.date_modified, orig_date_modified)
        self.assertEquals(self.system.fqdn, 'new.fqdn.name')

    def test_grants_view_permission_to_everybody_by_default(self):
        fqdn = data_setup.unique_name(u'test-csv-import%s.example.invalid')
        b = self.browser
        login(b)
        self.import_csv((u'csv_type,fqdn\n'
                u'system,%s' % fqdn).encode('utf8'))
        self.assertEquals(self.browser.find_element_by_xpath(
                '//table[@id="csv-import-log"]//td').text,
                'No Errors')
        with session.begin():
            system = System.query.filter(System.fqdn == fqdn).one()
            self.assertTrue(system.custom_access_policy.grants_everybody(
                    SystemPermission.view))

    def test_system_secret_field(self):
        login(self.browser)
        self.import_csv((u'csv_type,fqdn,secret\n'
                u'system,%s,True' % self.system.fqdn)
                .encode('utf8'))
        self.assertEquals(self.browser.find_element_by_xpath(
                '//table[@id="csv-import-log"]//td').text,
                'No Errors')
        with session.begin():
            session.refresh(self.system.custom_access_policy)
            self.assertFalse(self.system.custom_access_policy.grants_everybody(
                    SystemPermission.view))
        self.import_csv((u'csv_type,fqdn,secret\n'
                u'system,%s,False' % self.system.fqdn)
                .encode('utf8'))
        self.assertEquals(self.browser.find_element_by_xpath(
                '//table[@id="csv-import-log"]//td').text,
                'No Errors')
        with session.begin():
            session.refresh(self.system.custom_access_policy)
            self.assertTrue(self.system.custom_access_policy.grants_everybody(
                    SystemPermission.view))

    def test_keyvalue(self):
        login(self.browser)
        orig_date_modified = self.system.date_modified
        self.import_csv((u'csv_type,fqdn,key,key_value,deleted\n'
                u'keyvalue,%s,COMMENT,UTF 8 –,False' % self.system.fqdn)
                .encode('utf8'))
        self.failUnless(is_text_present(self.browser, "No Errors"))
        with session.begin():
            session.refresh(self.system)
            assert_has_key_with_value(self.system, 'COMMENT', u'UTF 8 –')
            self.assert_(self.system.date_modified > orig_date_modified)

    #https://bugzilla.redhat.com/show_bug.cgi?id=1058549
    def test_keyvalue_non_existent_system_valid(self):
        login(self.browser)
        fqdn = data_setup.unique_name('system%s.idonot.exist')
        self.import_csv((u'csv_type,fqdn,key,key_value,deleted\n'
                         u'keyvalue,%s,COMMENT,acomment,False' % fqdn)
                        .encode('utf8'))

        self.assertEquals(self.browser.find_element_by_xpath(
            '//table[@id="csv-import-log"]//td').text,
                          "No Errors")

        with session.begin():
            system = System.query.filter(System.fqdn == fqdn).one()
            assert_has_key_with_value(system, 'COMMENT', u'acomment')

    #https://bugzilla.redhat.com/show_bug.cgi?id=1058549
    def test_keyvalue_non_existent_system_valid_invalid(self):
        login(self.browser)
        fqdn = data_setup.unique_name('system%s.idonot.exist')
        self.import_csv((u'csv_type,fqdn,key,key_value,deleted\n'
                         u'keyvalue,%s,COMMENT,acomment,False\n' 
                         u'keyvalue,%s,COMMENT,acomment,False' % (fqdn, '--'+fqdn))
                        .encode('utf8'))

        self.assertEquals(self.browser.find_element_by_xpath(
            '//table[@id="csv-import-log"]//td').text,
                          "Error importing system on line 3: "
                          "System has an invalid FQDN: --%s"%fqdn)

        with session.begin():
            system = System.query.filter(System.fqdn == fqdn).one()
            assert_has_key_with_value(system, 'COMMENT', u'acomment')

    #https://bugzilla.redhat.com/show_bug.cgi?id=1058549
    def test_labinfo_non_existent_system(self):
        login(self.browser)
        fqdn = data_setup.unique_name('system%s.idonot.exist')
        self.import_csv((u'csv_type,fqdn,orig_cost,curr_cost,dimensions,weight,wattage,cooling\n'
                         u'labinfo,%s,10000,10000,3000,4000.0,5001.0,6000.0' % fqdn)
                        .encode('utf8'))
        with session.begin():
            system = System.query.filter(System.fqdn == fqdn).one()
            self.assertEqual(system.labinfo.orig_cost, Decimal('10000'))
            self.assertEqual(system.labinfo.curr_cost, Decimal('10000'))
            self.assertEqual(system.labinfo.dimensions, u'3000')
            self.assertEqual(system.labinfo.weight, 4000.0)
            self.assertEqual(system.labinfo.wattage, 5001.0)
            self.assertEqual(system.labinfo.cooling, 6000.0)

    #https://bugzilla.redhat.com/show_bug.cgi?id=1058549
    def test_power_non_existent_system(self):
        login(self.browser)
        fqdn = data_setup.unique_name('system%s.idonot.exist')
        self.import_csv((u'csv_type,fqdn,power_address,power_user,power_password,power_id,power_type\n'
                         u'power,%s,qemu+tcp://%s,admin,admin,%s,virsh' % ((fqdn, )*3))
                        .encode('utf8'))
        with session.begin():
            system = System.query.filter(System.fqdn == fqdn).one()
            self.assertEqual(system.power.power_id, fqdn)
            self.assertEqual(system.power.power_user, 'admin')
            self.assertEqual(system.power.power_address, 'qemu+tcp://' + fqdn)

    #https://bugzilla.redhat.com/show_bug.cgi?id=1058549
    def test_excluded_family_non_existent_system(self):
        login(self.browser)
        fqdn = data_setup.unique_name('system%s.idonot.exist')
        with session.begin():
            osmajor = OSMajor.lazy_create(osmajor=u'MyEnterpriseLinux')
        self.import_csv((u'csv_type,fqdn,arch,family,update,excluded\n'
                         u'exclude,%s,x86_64,MyEnterpriseLinux,,True' % 
                         fqdn)
                        .encode('utf8'))

        with session.begin():
            system = System.query.filter(System.fqdn == fqdn).one()
            self.assertEquals(system.excluded_osmajor[0].osmajor_id,
                              osmajor.id)

    #https://bugzilla.redhat.com/show_bug.cgi?id=1058549
    def test_install_options_non_existent_system(self):
        login(self.browser)
        fqdn = data_setup.unique_name('system%s.idonot.exist')
        with session.begin():
            distro_tree = data_setup.create_distro_tree(osmajor='MyEnterpriseLinux',
                                                        arch=u'x86_64')
        self.import_csv((u'csv_type,fqdn,arch,family,update,ks_meta,kernel_options,kernel_options_post\n'
                         u'install,%s,x86_64,MyEnterpriseLinux,,mode=cmdline,,console=ttyS0' % 
                         fqdn)
                        .encode('utf8'))

        with session.begin():
            system = System.query.filter(System.fqdn == fqdn).one()
            self.assertEqual(system.install_options(distro_tree).ks_meta['mode'],
                             'cmdline')
            self.assertEqual(system.install_options(distro_tree).kernel_options_post['console'],
                             'ttyS0')

    #https://bugzilla.redhat.com/show_bug.cgi?id=1058549
    def test_groups_non_existent_system(self):
        login(self.browser)
        fqdn = data_setup.unique_name('system%s.idonot.exist')
        with session.begin():
            group = data_setup.create_group()
        self.import_csv((u'csv_type,fqdn,group,deleted\n'
                         u'system_group,%s,%s,False' % 
                         (fqdn, group.group_name))
                        .encode('utf8'))

        with session.begin():
            system = System.query.filter(System.fqdn == fqdn).one()
            self.assertIn(group.group_name, 
                          [g.group_name for g in system.groups])

    # https://bugzilla.redhat.com/show_bug.cgi?id=787519
    def test_no_quotes(self):
        with session.begin():
            data_setup.create_labcontroller(fqdn=u'imhoff.bkr')
        b = self.browser
        login(b)
        b.get(get_server_base() + 'csv/csv_import')
        b.find_element_by_name('csv_file').send_keys(
                pkg_resources.resource_filename(self.__module__, 'bz787519.csv'))
        b.find_element_by_name('csv_file').submit()
        self.failUnless(is_text_present(self.browser, "No Errors"))

    # https://bugzilla.redhat.com/show_bug.cgi?id=802842
    def test_doubled_quotes(self):
        with session.begin():
            system = data_setup.create_system(fqdn=u'mymainframe.funtimes.invalid', arch=u's390x')
            OSMajor.lazy_create(osmajor=u'RedHatEnterpriseLinux7')
        b = self.browser
        login(b)
        b.get(get_server_base() + 'csv/csv_import')
        b.find_element_by_name('csv_file').send_keys(
                pkg_resources.resource_filename(self.__module__, 'bz802842.csv'))
        b.find_element_by_name('csv_file').submit()
        self.failUnless(is_text_present(self.browser, "No Errors"))
        with session.begin():
            session.refresh(system)
            self.assertEquals(system.provisions[Arch.by_name(u's390x')]\
                    .provision_families[OSMajor.by_name(u'RedHatEnterpriseLinux7')]\
                    .kernel_options,
                    'rd.znet="qeth,0.0.8000,0.0.8001,0.0.8002,layer2=1,portname=lol,portno=0" '
                    'ip=1.2.3.4::1.2.3.4:255.255.248.0::eth0:none MTU=1500 nameserver=1.2.3.4 '
                    'DASD=20A1,21A1,22A1,23A1 MACADDR=02:DE:AD:BE:EF:16 '
                    '!LAYER2 !DNS !PORTNO !IPADDR !GATEWAY !HOSTNAME !NETMASK ')

    def test_missing_field(self):
        login(self.browser)
        orig_date_modified = self.system.date_modified
        self.import_csv((u'csv_type,fqdn,location,arch\n'
                u'system,%s,Under my desk' % self.system.fqdn)
                .encode('utf8'))
        self.assert_(is_text_present(self.browser, 'Missing fields on line 2: arch'))

    def test_extraneous_field(self):
        login(self.browser)
        orig_date_modified = self.system.date_modified
        self.import_csv((u'csv_type,fqdn,location,arch\n'
                u'system,%s,Under my desk,ppc64,what is this field doing here' % self.system.fqdn)
                .encode('utf8'))
        self.assert_(is_text_present(self.browser, 'Too many fields on line 2 (expecting 4)'))

    # https://bugzilla.redhat.com/show_bug.cgi?id=972411
    def test_malformed(self):
        login(self.browser)
        self.import_csv('gar\x00bage')
        self.assertEquals(self.browser.find_element_by_xpath(
                '//table[@id="csv-import-log"]//td').text,
                'Error parsing CSV file: line contains NULL byte')

if __name__ == "__main__":
    unittest.main()
