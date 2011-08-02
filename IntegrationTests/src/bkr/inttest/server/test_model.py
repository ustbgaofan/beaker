import sys
import time
import unittest
import email
from turbogears.database import session
from bkr.server.model import System, SystemStatus, SystemActivity, TaskStatus, \
        SystemType, Job, JobCc, Key, Key_Value_Int, Key_Value_String, \
        Cpu, Numa, Provision, job_cc_table, Arch
from bkr.inttest import data_setup
from nose.plugins.skip import SkipTest

class SchemaSanityTest(unittest.TestCase):

    def test_all_tables_use_innodb(self):
        engine = session.get_bind(System.mapper)
        if engine.url.drivername != 'mysql':
            raise SkipTest('not using MySQL')
        for table in engine.table_names():
            self.assertEquals(engine.scalar(
                    'SELECT engine FROM information_schema.tables '
                    'WHERE table_schema = DATABASE() AND table_name = %s',
                    table), 'InnoDB')

class TestSystem(unittest.TestCase):

    def setUp(self):
        session.begin()

    def tearDown(self):
        session.rollback()
        session.close()

    def test_create_system_params(self):
        owner = data_setup.create_user()
        new_system = System(fqdn=u'test_fqdn', contact=u'test@email.com',
                            location=u'Brisbane', model=u'Proliant', serial=u'4534534',
                            vendor=u'Dell', type=SystemType.by_name(u'Machine'),
                            status=SystemStatus.by_name(u'Automated'),
                            owner=owner)
        session.flush()
        self.assertEqual(new_system.fqdn, 'test_fqdn')
        self.assertEqual(new_system.contact, 'test@email.com')
        self.assertEqual(new_system.location, 'Brisbane')
        self.assertEqual(new_system.model, 'Proliant')
        self.assertEqual(new_system.serial, '4534534')
        self.assertEqual(new_system.vendor, 'Dell')
        self.assertEqual(new_system.owner, owner)
    
    def test_add_user_to_system(self): 
        user = data_setup.create_user()
        system = data_setup.create_system()
        system.user = user
        session.flush()
        self.assertEquals(system.user, user)

    def test_remove_user_from_system(self):
        user = data_setup.create_user()
        system = data_setup.create_system()
        system.user = user
        system.user = None
        session.flush()
        self.assert_(system.user is None)

    def test_install_options_override(self):
        distro = data_setup.create_distro()
        system = data_setup.create_system()
        system.provisions[distro.arch] = Provision(
                kernel_options='console=ttyS0 ksdevice=eth0')
        opts = system.install_options(distro, kernel_options='ksdevice=eth1')
        # ksdevice should be overriden but console should be inherited
        self.assertEqual(opts['kernel_options'],
                dict(console='ttyS0', ksdevice='eth1'))

class TestSystemKeyValue(unittest.TestCase):

    def setUp(self):
        session.begin()

    def tearDown(self):
        session.rollback()

    def test_removing_key_type_cascades_to_key_value(self):
        # https://bugzilla.redhat.com/show_bug.cgi?id=647566
        string_key_type = Key(u'COLOUR', numeric=False)
        int_key_type = Key(u'FAIRIES', numeric=True)
        system = data_setup.create_system()
        system.key_values_string.append(
                Key_Value_String(string_key_type, u'pretty pink'))
        system.key_values_int.append(Key_Value_Int(int_key_type, 9000))
        session.flush()

        session.delete(string_key_type)
        session.delete(int_key_type)
        session.flush()

        session.clear()
        reloaded_system = System.query().get(system.id)
        self.assertEqual(reloaded_system.key_values_string, [])
        self.assertEqual(reloaded_system.key_values_int, [])

class TestBrokenSystemDetection(unittest.TestCase):

    # https://bugzilla.redhat.com/show_bug.cgi?id=637260
    # The 1-second sleeps here are so that the various timestamps
    # don't end up within the same second

    def setUp(self):
        self.system = data_setup.create_system()
        self.system.status = SystemStatus.by_name(u'Automated')
        data_setup.create_completed_job(system=self.system)
        session.flush()
        time.sleep(1)

    def abort_recipe(self, distro=None):
        if distro is None:
            distro = data_setup.create_distro()
            distro.tags.append(u'RELEASED')
        recipe = data_setup.create_recipe(distro=distro)
        data_setup.create_job_for_recipes([recipe])
        recipe.system = self.system
        recipe.tasks[0].status = TaskStatus.by_name(u'Running')
        recipe.update_status()
        session.flush()
        recipe.abort()

    def test_multiple_suspicious_aborts_triggers_broken_system(self):
        # first aborted recipe shouldn't trigger it
        self.abort_recipe()
        self.assertNotEqual(self.system.status, SystemStatus.by_name(u'Broken'))
        # another recipe with a different stable distro *should* trigger it
        self.abort_recipe()
        self.assertEqual(self.system.status, SystemStatus.by_name(u'Broken'))

    def test_status_change_is_respected(self):
        # two aborted recipes should trigger it...
        self.abort_recipe()
        self.abort_recipe()
        self.assertEqual(self.system.status, SystemStatus.by_name(u'Broken'))
        # then the owner comes along and marks it as fixed...
        self.system.status = SystemStatus.by_name(u'Automated')
        self.system.activity.append(SystemActivity(service=u'WEBUI',
                action=u'Changed', field_name=u'Status',
                old_value=u'Broken',
                new_value=unicode(self.system.status)))
        session.flush()
        time.sleep(1)
        # another recipe aborts...
        self.abort_recipe()
        self.assertNotEqual(self.system.status, SystemStatus.by_name(u'Broken')) # not broken! yet
        self.abort_recipe()
        self.assertEqual(self.system.status, SystemStatus.by_name(u'Broken')) # now it is

    def test_counts_distinct_stable_distros(self):
        first_distro = data_setup.create_distro()
        first_distro.tags.append(u'RELEASED')
        # two aborted recipes for the same distro shouldn't trigger it
        self.abort_recipe(distro=first_distro)
        self.abort_recipe(distro=first_distro)
        self.assertNotEqual(self.system.status, SystemStatus.by_name(u'Broken'))
        # .. but a different distro should
        self.abort_recipe()
        self.assertEqual(self.system.status, SystemStatus.by_name(u'Broken'))

    def test_updates_modified_date(self):
        orig_date_modified = self.system.date_modified
        self.abort_recipe()
        self.abort_recipe()
        self.assertEqual(self.system.status, SystemStatus.by_name(u'Broken'))
        self.assert_(self.system.date_modified > orig_date_modified)

class TestJob(unittest.TestCase):

    def test_cc_property(self):
        session.begin()
        try:
            job = data_setup.create_job()
            session.flush()
            session.execute(job_cc_table.insert(values={'job_id': job.id,
                    'email_address': u'person@nowhere.example.com'}))
            session.refresh(job)
            self.assertEquals(job.cc, ['person@nowhere.example.com'])

            job.cc.append(u'korolev@nauk.su')
            session.flush()
            self.assertEquals(JobCc.query().filter_by(job_id=job.id).count(), 2)
        finally:
            session.rollback()

class DistroTest(unittest.TestCase):

    def setUp(self):
        self.distro = data_setup.create_distro(arch=u'i386')
        self.lc = data_setup.create_labcontroller()
        session.flush()

    def test_all_systems_obeys_osmajor_exclusions(self):
        included_system = data_setup.create_system(arch=u'i386',
                lab_controller=self.lc)
        excluded_system = data_setup.create_system(arch=u'i386',
                lab_controller=self.lc,
                exclude_osmajor=[self.distro.osversion.osmajor])
        excluded_system.arch.append(Arch.by_name(u'x86_64'))
        session.flush()
        systems = self.distro.all_systems().all()
        self.assert_(included_system in systems and
                excluded_system not in systems, systems)

    def test_all_systems_obeys_osversion_exclusions(self):
        included_system = data_setup.create_system(arch=u'i386',
                lab_controller=self.lc)
        excluded_system = data_setup.create_system(arch=u'i386',
                lab_controller=self.lc,
                exclude_osversion=[self.distro.osversion])
        excluded_system.arch.append(Arch.by_name(u'x86_64'))
        session.flush()
        systems = self.distro.all_systems().all()
        self.assert_(included_system in systems and
                excluded_system not in systems, systems)

    def test_all_systems_matches_arch(self):
        included_system = data_setup.create_system(arch=u'i386',
                lab_controller=self.lc)
        excluded_system = data_setup.create_system(arch=u'ppc64',
                lab_controller=self.lc)
        session.flush()
        systems = self.distro.all_systems().all()
        self.assert_(included_system in systems and
                excluded_system not in systems, systems)

class DistroSystemsFilterTest(unittest.TestCase):

    def setUp(self):
        self.lc = data_setup.create_labcontroller()
        self.distro = data_setup.create_distro(arch=u'i386')
        self.user = data_setup.create_user()
        session.flush()

    def test_cpu_count(self):
        excluded = data_setup.create_system(arch=u'i386', shared=True)
        excluded.lab_controller = self.lc
        excluded.cpu = Cpu(processors=1)
        included = data_setup.create_system(arch=u'i386', shared=True)
        included.cpu = Cpu(processors=4)
        included.lab_controller = self.lc
        session.flush()
        systems = list(self.distro.systems_filter(self.user, """
            <hostRequires>
                <and>
                    <cpu_count op="=" value="4" />
                </and>
            </hostRequires>
            """))
        self.assert_(excluded not in systems)
        self.assert_(included in systems)
        systems = list(self.distro.systems_filter(self.user, """
            <hostRequires>
                <and>
                    <cpu_count op="&gt;" value="2" />
                    <cpu_count op="&lt;" value="5" />
                </and>
            </hostRequires>
            """))
        self.assert_(excluded not in systems)
        self.assert_(included in systems)

    def test_or_lab_controller(self):
        lc1 = data_setup.create_labcontroller(fqdn=u'lab1')
        lc2 = data_setup.create_labcontroller(fqdn=u'lab2')
        lc3 = data_setup.create_labcontroller(fqdn=u'lab3')
        distro = data_setup.create_distro()
        included = data_setup.create_system(arch=u'i386', shared=True)
        included.lab_controller = lc1
        excluded = data_setup.create_system(arch=u'i386', shared=True)
        excluded.lab_controller = lc3
        session.flush()
        systems = list(distro.systems_filter(self.user, """
               <hostRequires>
                <or>
                 <hostlabcontroller op="=" value="lab1"/>
                 <hostlabcontroller op="=" value="lab2"/>
                </or>
               </hostRequires>
            """))
        self.assert_(excluded not in systems)
        self.assert_(included in systems)


    def test_numa_node_count(self):
        excluded = data_setup.create_system(arch=u'i386', shared=True)
        excluded.lab_controller = self.lc
        excluded.numa = Numa(nodes=1)
        included = data_setup.create_system(arch=u'i386', shared=True)
        included.numa = Numa(nodes=64)
        included.lab_controller = self.lc
        session.flush()
        systems = list(self.distro.systems_filter(self.user, """
            <hostRequires>
                <and>
                    <numa_node_count op=">=" value="32" />
                </and>
            </hostRequires>
            """))
        self.assert_(excluded not in systems)
        self.assert_(included in systems)

    # https://bugzilla.redhat.com/show_bug.cgi?id=679879
    def test_key_notequal(self):
        module_key = Key.by_name(u'MODULE')
        with_cciss = data_setup.create_system(arch=u'i386', shared=True)
        with_cciss.lab_controller = self.lc
        with_cciss.key_values_string.extend([
                Key_Value_String(module_key, u'cciss'),
                Key_Value_String(module_key, u'kvm')])
        without_cciss = data_setup.create_system(arch=u'i386', shared=True)
        without_cciss.lab_controller = self.lc
        without_cciss.key_values_string.extend([
                Key_Value_String(module_key, u'ida'),
                Key_Value_String(module_key, u'kvm')])
        session.flush()
        systems = list(self.distro.systems_filter(self.user, """
            <hostRequires>
                <and>
                    <key_value key="MODULE" op="!=" value="cciss"/>
                </and>
            </hostRequires>
            """))
        self.assert_(with_cciss not in systems)
        self.assert_(without_cciss in systems)

    # https://bugzilla.redhat.com/show_bug.cgi?id=714974
    def test_hypervisor(self):
        baremetal = data_setup.create_system(arch=u'i386', shared=True,
                lab_controller=self.lc, hypervisor=None)
        kvm = data_setup.create_system(arch=u'i386', shared=True,
                lab_controller=self.lc, hypervisor=u'KVM')
        session.flush()
        systems = list(self.distro.systems_filter(self.user, """
            <hostRequires>
                <and>
                    <hypervisor op="=" value="KVM" />
                </and>
            </hostRequires>
            """))
        self.assert_(baremetal not in systems)
        self.assert_(kvm in systems)
        systems = list(self.distro.systems_filter(self.user, """
            <hostRequires>
                <and>
                    <hypervisor op="=" value="" />
                </and>
            </hostRequires>
            """))
        self.assert_(baremetal in systems)
        self.assert_(kvm not in systems)
        systems = list(self.distro.systems_filter(self.user, """
            <hostRequires/>
            """))
        self.assert_(baremetal in systems)
        self.assert_(kvm in systems)

if __name__ == '__main__':
    unittest.main()