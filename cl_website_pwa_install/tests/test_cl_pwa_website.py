# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64

from PIL import Image

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.image import image_to_base64

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def _image(width, height=None, output_format='PNG'):
    image = Image.new('RGB', (width, height or width), color=(20, 120, 200))
    return image_to_base64(image, output_format)


def _png(width, height=None):
    return _image(width, height)


@tagged('post_install', '-at_install')
class TestClPwaWebsite(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Website = cls.env['website']
        cls.website = Website.create({
            'name': 'PWA Shop',
            'favicon': Website._default_favicon(),
        })

    def test_manifest_defaults(self):
        manifest = self.website._cl_pwa_manifest()
        self.assertEqual(manifest['name'], 'PWA Shop', "App name defaults to the website name.")
        self.assertEqual(manifest['short_name'], 'PWA Shop')
        self.assertEqual(manifest['start_url'], '/')
        self.assertEqual(manifest['scope'], '/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['theme_color'], '#ffffff')
        self.assertEqual(manifest['background_color'], '#ffffff')
        # Odoo's default favicon is 16 px: too small for an app, so the Odoo logo is used.
        self.assertLess(self.website.cl_pwa_favicon_size, 144)
        self.assertEqual(
            [icon['src'] for icon in manifest['icons']],
            ['/web/static/img/odoo-icon-192x192.png', '/web/static/img/odoo-icon-512x512.png'])
        self.assertFalse(self.website.cl_pwa_favicon_icon)
        self.assertEqual(self.website._cl_pwa_apple_touch_icon_url(), '/web/static/img/odoo-icon-ios.png')

    def test_manifest_configured(self):
        self.website.write({
            'cl_pwa_name': 'PWA Shop App',
            'cl_pwa_short_name': 'Shop',
            'cl_pwa_theme_color': '#1f6feb',
            'cl_pwa_background_color': '#000',
            'cl_pwa_icon': _png(600),
        })
        self.assertEqual(self.website.cl_pwa_icon_size, 512, "The icon is stored at 512 px at most.")
        manifest = self.website._cl_pwa_manifest()
        self.assertEqual(manifest['name'], 'PWA Shop App')
        self.assertEqual(manifest['short_name'], 'Shop')
        self.assertEqual(manifest['theme_color'], '#1f6feb')
        self.assertEqual(manifest['background_color'], '#000')
        self.assertEqual([icon['sizes'] for icon in manifest['icons']], ['192x192', '512x512'])
        for icon in manifest['icons']:
            self.assertTrue(icon['src'].startswith(
                '/web/image/website/%s/cl_pwa_icon/%s?unique=' % (self.website.id, icon['sizes'])))
            self.assertTrue(icon['src'].endswith('&crop=1'))
            # Chrome and Edge refuse an icon whose type they cannot tell.
            self.assertEqual(icon['type'], 'image/png')
            self.assertEqual(icon['purpose'], 'any')
        self.assertIn('/cl_pwa_icon/180x180', self.website._cl_pwa_apple_touch_icon_url())

    def test_icon_is_stored_as_png(self):
        # A JPEG is not accepted by browsers as an app icon.
        self.website.cl_pwa_icon = _image(400, output_format='JPEG')
        stored = base64.b64decode(self.website.with_context(bin_size=False).cl_pwa_icon)
        self.assertTrue(stored.startswith(PNG_SIGNATURE))
        self.assertEqual(self.website.cl_pwa_icon_size, 400)
        other = self.env['website'].create({'name': 'Created With Icon', 'cl_pwa_icon': _image(256, output_format='JPEG')})
        stored = base64.b64decode(other.with_context(bin_size=False).cl_pwa_icon)
        self.assertTrue(stored.startswith(PNG_SIGNATURE))

    def test_unreadable_icon_is_refused(self):
        with self.assertRaises(UserError):
            self.website.cl_pwa_icon = base64.b64encode(b'this is not an image')

    def test_icon_sizes_never_exceed_the_image(self):
        self.website.cl_pwa_icon = _png(300, 400)
        self.assertEqual(self.website.cl_pwa_icon_size, 300)
        icons = self.website._cl_pwa_manifest_icons()
        self.assertEqual([icon['sizes'] for icon in icons], ['192x192', '300x300'])

    def test_icon_too_small(self):
        with self.assertRaises(ValidationError):
            self.website.cl_pwa_icon = _png(100)

    def test_large_favicon_is_the_fallback(self):
        # Odoo stores favicons as 256 x 256 ICO files at most.
        self.website.favicon = _png(400)
        self.assertEqual(self.website.cl_pwa_favicon_size, 256)
        # ...which no browser takes as an app icon: a PNG copy is served.
        copy = base64.b64decode(self.website.with_context(bin_size=False).cl_pwa_favicon_icon)
        self.assertTrue(copy.startswith(PNG_SIGNATURE))
        icons = self.website._cl_pwa_manifest_icons()
        self.assertEqual([icon['sizes'] for icon in icons], ['192x192', '256x256'])
        for icon in icons:
            self.assertEqual(icon['type'], 'image/png')
            self.assertTrue(icon['src'].startswith(
                '/web/image/website/%s/cl_pwa_favicon_icon/%s?unique=' % (self.website.id, icon['sizes'])))
        self.assertIn('/cl_pwa_favicon_icon/180x180', self.website._cl_pwa_apple_touch_icon_url())
        # A small favicon again: the copy goes away.
        self.website.favicon = _png(64)
        self.assertFalse(self.website.cl_pwa_favicon_icon)
        self.assertIn('odoo-icon', self.website._cl_pwa_manifest_icons()[0]['src'])
        self.website.favicon = _png(400)
        # An app icon, once set, wins over the favicon.
        self.website.cl_pwa_icon = _png(512)
        self.assertIn('/cl_pwa_icon/', self.website._cl_pwa_manifest_icons()[0]['src'])

    def test_colors_are_validated(self):
        for color in ('blue', '#12345', '1f6feb', '#1f6feb; color: red'):
            with self.subTest(color=color), self.assertRaises(ValidationError):
                self.website.cl_pwa_theme_color = color

    def test_settings_are_per_website(self):
        other = self.env['website'].create({'name': 'Other Shop'})
        self.website.cl_pwa_name = 'PWA Shop App'
        self.assertEqual(other._cl_pwa_manifest()['name'], 'Other Shop')
        self.assertEqual(self.website._cl_pwa_manifest()['name'], 'PWA Shop App')
