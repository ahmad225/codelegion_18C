# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Website App Install (PWA)',
    'summary': 'Let visitors install your website as an app: web manifest, '
               'service worker and an install invitation on the homepage.',
    'description': """
Website App Install (PWA)
=========================
Turn each of your websites into an installable app (Progressive Web App).

* **Per-website settings** in Website > Configuration > Settings: switch it on,
  app name and short name, theme and background colours, and an app icon.
* **Web app manifest** for every website, with its own name, colours and
  icons. Icons are served and resized by Odoo's standard image route, so they
  are cached by the browser, and they are always PNG (the format browsers
  require): an uploaded icon is saved as PNG and a large favicon gets a PNG
  copy.
* **Service worker** that makes the site installable. It never invents
  responses: pages load from the network as usual, and only a page that
  cannot be reached while offline shows a short "You are offline" notice.
* **Install invitation** on the homepage:

  * Chrome, Edge and Android: an *Install* button that opens the browser's
    own install dialog - shown only when the browser says the site can be
    installed.
  * iPhone / iPad (Safari): the steps for *Share > Add to Home Screen*.
  * Mac (Safari 17 or later): the steps for *Add to Dock*.
  * Other browsers, visitors already using the installed app, and pages
    shown inside a frame (such as the website editor's preview): nothing.

* **Respects the visitor**: *Not now* hides it for the rest of the visit,
  *Don't show again* hides it on that device.
* **Accessible**: a proper dialog with keyboard support (Tab, Escape) and a
  focusable close button. All texts are translatable.
* Works with any theme - no dependency on a third-party theme.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Website/Website',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['website'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/website_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'cl_website_pwa_install/static/src/scss/cl_pwa_install.scss',
            'cl_website_pwa_install/static/src/js/cl_pwa_service_worker.js',
            'cl_website_pwa_install/static/src/js/cl_pwa_install.js',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
