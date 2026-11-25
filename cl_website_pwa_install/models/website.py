# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
import binascii
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.image import base64_to_image, image_process

DEFAULT_COLOR = '#ffffff'
HEX_COLOR_RE = re.compile(r'#(?:[0-9a-fA-F]{3}){1,2}')

# The app icon must be at least this big (shorter side, in pixels).
CL_PWA_ICON_MIN_PX = 192
# Smallest icon browsers accept as the main icon of an installable app
# (Chrome's rule). A smaller favicon is not used as the app icon.
CL_PWA_INSTALL_ICON_MIN_PX = 144

ODOO_MANIFEST_ICONS = [
    {'src': '/web/static/img/odoo-icon-192x192.png', 'sizes': '192x192',
     'type': 'image/png', 'purpose': 'any'},
    {'src': '/web/static/img/odoo-icon-512x512.png', 'sizes': '512x512',
     'type': 'image/png', 'purpose': 'any'},
]
ODOO_APPLE_TOUCH_ICON = '/web/static/img/odoo-icon-ios.png'
ODOO_DIALOG_ICON = '/web/static/img/odoo-icon-192x192.png'
# Chrome and Edge only accept PNG, SVG or WebP icons for an installable app,
# and they must be told the type: our image URLs have no file extension.
CL_PWA_ICON_MIMETYPE = 'image/png'


def _image_px(base64_value):
    """Shorter side, in pixels, of a base64 image; 0 when empty or unreadable."""
    if not base64_value:
        return 0
    try:
        return min(base64_to_image(base64_value).size)
    except (UserError, ValueError, OSError):
        return 0


def _to_png(base64_value, size=(0, 0)):
    """The base64 image as a base64 PNG, at most `size` pixels."""
    return base64.b64encode(
        image_process(base64.b64decode(base64_value), size=size, output_format='PNG'))


class Website(models.Model):
    _inherit = 'website'

    cl_pwa_enabled = fields.Boolean(
        string='Offer App Install',
        help="Let visitors install this website as an app, and invite them to "
             "do so on the homepage.")
    cl_pwa_name = fields.Char(
        string='App Name',
        help="Name of the installed app. Leave empty to use the website name.")
    cl_pwa_short_name = fields.Char(
        string='App Short Name',
        help="Shown where space is short, such as under the icon on a phone's "
             "home screen (about 12 characters). Leave empty to use the app name.")
    cl_pwa_theme_color = fields.Char(
        string='App Theme Color', default=DEFAULT_COLOR,
        help="Color of the title bar of the installed app and of the browser "
             "toolbar on mobile.")
    cl_pwa_background_color = fields.Char(
        string='App Background Color', default=DEFAULT_COLOR,
        help="Color of the splash screen shown while the app starts.")
    cl_pwa_icon = fields.Image(
        string='App Icon', max_width=512, max_height=512,
        help="Square image of at least 192 x 192 pixels (512 x 512 recommended). "
             "It is saved as a PNG. Leave empty to use the favicon when it is "
             "large enough, otherwise the Odoo logo.")
    # Worked out once when the image changes so that rendering a page or the
    # manifest never has to open the image itself.
    cl_pwa_icon_size = fields.Integer(
        compute='_compute_cl_pwa_icon_size', store=True)
    cl_pwa_favicon_size = fields.Integer(
        compute='_compute_cl_pwa_favicon_icon', store=True)
    # Odoo stores the favicon as an ICO file, which browsers refuse as an app
    # icon: keep a PNG copy of a favicon that is large enough to be one.
    cl_pwa_favicon_icon = fields.Image(
        compute='_compute_cl_pwa_favicon_icon', store=True)

    @api.depends('cl_pwa_icon')
    def _compute_cl_pwa_icon_size(self):
        for website in self:
            website.cl_pwa_icon_size = _image_px(
                website.with_context(bin_size=False).cl_pwa_icon)

    @api.depends('favicon')
    def _compute_cl_pwa_favicon_icon(self):
        for website in self:
            favicon = website.with_context(bin_size=False).favicon
            size = _image_px(favicon)
            icon = False
            if size >= CL_PWA_INSTALL_ICON_MIN_PX:
                try:
                    icon = _to_png(favicon)
                except (UserError, ValueError, OSError):
                    size = 0
            website.cl_pwa_favicon_size = size
            website.cl_pwa_favicon_icon = icon

    @api.model
    def _cl_pwa_prepare_icon(self, vals):
        """Store the app icon as a PNG, whatever format was uploaded."""
        if vals.get('cl_pwa_icon'):
            try:
                vals['cl_pwa_icon'] = _to_png(vals['cl_pwa_icon'], size=(512, 512))
            except (binascii.Error, ValueError, OSError) as error:
                raise UserError(_("The app icon could not be read as an image.")) from error

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._cl_pwa_prepare_icon(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._cl_pwa_prepare_icon(vals)
        return super().write(vals)

    @api.constrains('cl_pwa_theme_color', 'cl_pwa_background_color')
    def _check_cl_pwa_colors(self):
        for website in self:
            for color in (website.cl_pwa_theme_color, website.cl_pwa_background_color):
                if color and not HEX_COLOR_RE.fullmatch(color):
                    raise ValidationError(_(
                        "App colors must be hexadecimal colors such as #1f6feb, not %s.",
                        color))

    @api.constrains('cl_pwa_icon')
    def _check_cl_pwa_icon(self):
        for website in self:
            if (website.with_context(bin_size=True).cl_pwa_icon
                    and website.cl_pwa_icon_size < CL_PWA_ICON_MIN_PX):
                raise ValidationError(_(
                    "The app icon must be at least %(size)s x %(size)s pixels.",
                    size=CL_PWA_ICON_MIN_PX))

    # ------------------------------------------------------------------
    # Values used by the manifest, the page head and the install dialog
    # ------------------------------------------------------------------

    def _cl_pwa_app_name(self):
        self.ensure_one()
        return (self.cl_pwa_name or '').strip() or self.name

    def _cl_pwa_app_short_name(self):
        self.ensure_one()
        return (self.cl_pwa_short_name or '').strip() or self._cl_pwa_app_name()

    def _cl_pwa_icon_source(self):
        """(field name, size in pixels) of the PNG to use as the app icon:
        the app icon, else the favicon when it is big enough, else nothing."""
        self.ensure_one()
        if self.cl_pwa_icon_size:
            return 'cl_pwa_icon', self.cl_pwa_icon_size
        if self.cl_pwa_favicon_size >= CL_PWA_INSTALL_ICON_MIN_PX:
            return 'cl_pwa_favicon_icon', self.cl_pwa_favicon_size
        return False, 0

    def _cl_pwa_icon_url(self, size):
        """Square PNG of at most `size` pixels, resized and cached by Odoo's
        /web/image route; False when the website has no usable icon."""
        self.ensure_one()
        field, available = self._cl_pwa_icon_source()
        if not field:
            return False
        size = min(size, available)
        return '%s&crop=1' % self.image_url(self, field, '%sx%s' % (size, size))

    def _cl_pwa_apple_touch_icon_url(self):
        return self._cl_pwa_icon_url(180) or ODOO_APPLE_TOUCH_ICON

    def _cl_pwa_dialog_icon_url(self):
        return self._cl_pwa_icon_url(128) or ODOO_DIALOG_ICON

    def _cl_pwa_manifest_icons(self):
        self.ensure_one()
        field, available = self._cl_pwa_icon_source()
        if not field:
            return [dict(icon) for icon in ODOO_MANIFEST_ICONS]
        # Never announce a size larger than the image really is.
        sizes = sorted({min(CL_PWA_ICON_MIN_PX, available), min(available, 512)})
        return [{
            'src': self._cl_pwa_icon_url(size),
            'sizes': '%sx%s' % (size, size),
            'type': CL_PWA_ICON_MIMETYPE,
            'purpose': 'any',
        } for size in sizes]

    def _cl_pwa_manifest(self):
        """Content of the web app manifest of this website."""
        self.ensure_one()
        return {
            'id': '/',
            'name': self._cl_pwa_app_name(),
            'short_name': self._cl_pwa_app_short_name(),
            'start_url': '/',
            'scope': '/',
            'display': 'standalone',
            'theme_color': self.cl_pwa_theme_color or DEFAULT_COLOR,
            'background_color': self.cl_pwa_background_color or DEFAULT_COLOR,
            'icons': self._cl_pwa_manifest_icons(),
            'prefer_related_applications': False,
        }
