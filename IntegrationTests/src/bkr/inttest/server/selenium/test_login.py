
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import sys
import os
import turbogears.config
from turbogears.database import session
import unittest
import xmlrpclib
from hashlib import sha1
from nose.plugins.skip import SkipTest
try:
    import krbV
except ImportError:
    krbV = None
from bkr.inttest import data_setup, with_transaction, get_server_base
from bkr.inttest.server.selenium import WebDriverTestCase, XmlRpcTestCase
from bkr.inttest.server.webdriver_utils import login

class LoginTest(WebDriverTestCase):

    password = u'password'

    @with_transaction
    def setUp(self):
        self.user = data_setup.create_user(password=self.password)
        self.browser = self.get_browser()

    def tearDown(self):
        self.browser.quit()

    # https://bugzilla.redhat.com/show_bug.cgi?id=660527
    def test_referer_redirect(self):
        with session.begin():
            system = data_setup.create_system()

        # Go to the system page
        b = self.browser
        b.get(get_server_base())
        b.find_element_by_name('simplesearch').send_keys(system.fqdn)
        b.find_element_by_id('simpleform').submit()
        b.find_element_by_link_text(system.fqdn).click()
        b.find_element_by_xpath('//title[text()="%s"]' % system.fqdn)

        # Click log in, and fill in details
        b.find_element_by_link_text('Log in').click()
        b.find_element_by_name('user_name').send_keys(self.user.user_name)
        b.find_element_by_name('password').send_keys(self.password)
        b.find_element_by_name('login').click()

        # We should be back at the system page
        b.find_element_by_xpath('//title[text()="%s"]' % system.fqdn)

    # https://bugzilla.redhat.com/show_bug.cgi?id=663277
    def test_NestedVariablesFilter_redirect(self):
        b = self.browser
        # Open jobs/mine (which requires login) with some funky params
        b.get(get_server_base() + 'jobs/mine?'
                'jobsearch-0.table=Status&'
                'jobsearch-0.operation=is+not&'
                'jobsearch-0.value=Completed&'
                'jobsearch-1.table=Status&'
                'jobsearch-1.operation=is+not&'
                'jobsearch-1.value=Cancelled')
        # Fill in the login form
        b.find_element_by_name('user_name').send_keys(self.user.user_name)
        b.find_element_by_name('password').send_keys(self.password)
        b.find_element_by_name('login').click()
        # Did it work?
        b.find_element_by_xpath('//title[text()="My Jobs"]')

    # https://bugzilla.redhat.com/show_bug.cgi?id=674566

    def test_message_when_not_logged_in(self):
        b = self.browser
        b.get(get_server_base() + 'jobs/mine')
        # XXX should check for 403 response code
        self.assertEquals(b.find_element_by_css_selector('#message').text,
                'Please log in.')

    def test_message_when_explicitly_logging_in(self):
        b = self.browser
        b.get(get_server_base())
        b.find_element_by_link_text('Log in').click()
        self.assertEquals(b.find_element_by_css_selector('#message').text,
                'Please log in.')

    def test_message_when_permissions_insufficient(self):
        b = self.browser
        login(b, self.user.user_name, self.password)
        b.get(get_server_base() + 'labcontrollers')
        # XXX should check for 403 response code
        b.find_element_by_xpath('//title[text()="Forbidden"]')
        self.assertEquals(b.find_element_by_css_selector('#reasons').text,
                'Not member of group: admin')

    def test_message_when_password_mistyped(self):
        b = self.browser
        login(b, self.user.user_name, 'not the right password')
        self.assertEquals(b.find_element_by_css_selector('#message').text,
                'The credentials you supplied were not correct or '
                'did not grant access to this resource.')

    # https://bugzilla.redhat.com/show_bug.cgi?id=994751
    def test_old_password_hashes_are_migrated(self):
        with session.begin():
            # unsalted SHA1 is the old hash format from TurboGears 1.0
            self.user._password = sha1(self.password).hexdigest()
        b = self.browser
        login(b, self.user.user_name, self.password)
        b.find_element_by_xpath('//title[text()="Systems"]')
        with session.begin():
            session.refresh(self.user)
            self.assert_(self.user._password.startswith('$pbkdf2-sha512$'),
                    self.user._password)

class XmlRpcLoginTest(XmlRpcTestCase):

    def test_krb_login(self):
        if not krbV:
            raise SkipTest('krbV module not found')
        server_princ_name = turbogears.config.get(
                'identity.krb_auth_principal', None)
        if not server_princ_name: # XXX FIXME dead test
            raise SkipTest('server not configured for krbV')

        # build krb request
        ctx = krbV.default_context()
        try:
            ccache = ctx.default_ccache()
            client_princ = ccache.principal()
        except krbV.Krb5Error:
            raise SkipTest('client ticket not found, run kinit first')
        server_princ = krbV.Principal(name=server_princ_name, context=ctx)
        ac = krbV.AuthContext(context=ctx)
        ac.flags = krbV.KRB5_AUTH_CONTEXT_DO_SEQUENCE | krbV.KRB5_AUTH_CONTEXT_DO_TIME
        ac.rcache = ctx.default_rcache()
        ac, req = ctx.mk_req(server=sprinc, client=cprinc, auth_context=ac,
                ccache=ccache, options=krbV.AP_OPTS_MUTUAL_REQUIRED)
        encoded_req = base64.encodestring(req)

        # attempt to log in
        server = self.get_server()
        server.auth.login_krbv(encoded_req)

    def test_password_login(self):
        with session.begin():
            user = data_setup.create_user(password=u'lulz')
        server = self.get_server()
        server.auth.login_password(user.user_name, u'lulz')
        who_am_i = server.auth.who_am_i()
        self.assertEquals(who_am_i['username'], user.user_name)

    def test_password_proxy_login(self):
        with session.begin():
            group = data_setup.create_group(permissions=[u'proxy_auth'])
            user = data_setup.create_user(password=u'lulz')
            proxied_user = data_setup.create_user(password=u'not_used')
            data_setup.add_user_to_group(user, group)
        server = self.get_server()
        server.auth.login_password(user.user_name, u'lulz', proxied_user.user_name)
        who_am_i = server.auth.who_am_i()
        self.assertEquals(who_am_i['username'], proxied_user.user_name)
        self.assertEquals(who_am_i['proxied_by_username'], user.user_name)

    # https://bugzilla.redhat.com/show_bug.cgi?id=660529
    def test_login_required_message(self):
        server = self.get_server()
        try:
            server.auth.who_am_i()
            self.fail('should raise')
        except xmlrpclib.Fault, e:
            self.assert_('Anonymous access denied' in e.faultString, e.faultString)
