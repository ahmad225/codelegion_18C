# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from lxml import html

from odoo.tests import HttpCase, tagged

MANIFEST_URL = '/cl_pwa/manifest.webmanifest'
SW_URL = '/cl_pwa/sw.js'


@tagged('post_install', '-at_install')
class TestClPwaRoutes(HttpCase):

    def setUp(self):
        super().setUp()
        # Whichever website answers the test requests, it is configured.
        self.websites = self.env['website'].search([])
        self.websites.write({
            'cl_pwa_enabled': True,
            'cl_pwa_name': 'CL Test App',
            'cl_pwa_theme_color': '#1f6feb',
        })

    def test_manifest_route(self):
        response = self.url_open(MANIFEST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['Content-Type'].startswith('application/manifest+json'))
        manifest = response.json()
        self.assertEqual(manifest['name'], 'CL Test App')
        self.assertEqual(manifest['start_url'], '/')
        self.assertEqual(manifest['scope'], '/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['theme_color'], '#1f6feb')
        self.assertTrue(manifest['icons'])
        for icon in manifest['icons']:
            self.assertTrue(icon['src'].startswith('/web/'))
            self.assertRegex(icon['sizes'], r'^\d+x\d+$')
            self.assertEqual(icon['type'], 'image/png')

    def test_service_worker_route(self):
        response = self.url_open(SW_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['Content-Type'].startswith('text/javascript'))
        self.assertEqual(response.headers.get('Service-Worker-Allowed'), '/')
        body = response.text
        self.assertIn('addEventListener("fetch"', body)
        self.assertIn('request.mode !== "navigate"', body, "Only page navigations are handled.")
        self.assertIn('You are offline', body)
        self.assertNotIn('caches.', body, "Nothing else is cached by the worker.")

    def test_page_markup_when_enabled(self):
        homepage = self.url_open('/')
        self.assertEqual(homepage.status_code, 200)
        self.assertIn('<link rel="manifest" href="%s"' % MANIFEST_URL, homepage.text)
        self.assertIn('<meta name="theme-color" content="#1f6feb"', homepage.text)
        self.assertIn('id="cl_pwa_install"', homepage.text)
        self.assertIn('role="dialog"', homepage.text)
        # Odoo only starts frontend widgets found inside #wrapwrap: anywhere
        # else, the dialog would stay hidden for ever.
        page = html.fromstring(homepage.text)
        self.assertEqual(len(page.xpath("//div[@id='wrapwrap']//div[@id='cl_pwa_install']")), 1)
        self.assertTrue(page.xpath("//div[@id='cl_pwa_install']/@hidden"))
        # Other pages: installable, but no install dialog.
        contactus = self.url_open('/contactus')
        self.assertEqual(contactus.status_code, 200)
        self.assertIn('<link rel="manifest" href="%s"' % MANIFEST_URL, contactus.text)
        self.assertNotIn('id="cl_pwa_install"', contactus.text)

    def test_disabled_website(self):
        self.websites.write({'cl_pwa_enabled': False})
        homepage = self.url_open('/')
        self.assertEqual(homepage.status_code, 200)
        self.assertNotIn(MANIFEST_URL, homepage.text)
        self.assertNotIn('beforeinstallprompt', homepage.text)
        self.assertNotIn('id="cl_pwa_install"', homepage.text)
        self.assertEqual(self.url_open(MANIFEST_URL).status_code, 404)
        self.assertEqual(self.url_open(SW_URL).status_code, 404)
