# Website App Install (PWA) (`cl_website_pwa_install`)

Let visitors install your website as an app, with an install invitation on the homepage. By [Code Legion](https://thecodelegion.com).

Each website gets its own app manifest, icon and colours, and the homepage invites visitors to install it: a one-click Install on Chrome, Edge and Android, and clear steps on iPhone, iPad and Mac Safari.

## What it does

- **Install button**: On Chrome, Edge and Android, shown only when the browser says the site can be installed.
- **iPhone, iPad and Mac**: Simple "Add to Home Screen" and "Add to Dock" steps for Safari.
- **Your name, icon and colours**: Per website, in Website settings. Falls back to the favicon or the Odoo logo.
- **Respects visitors**: "Not now" hides it for the visit, "Don't show again" on that device. Keyboard accessible.

## Behaves well

- Works with any theme: no dependency on a third-party theme, and no theme settings overridden.
- The service worker never fakes responses: pages load normally, and only an unreachable page shows an offline notice.
- Nothing is shown on browsers that cannot install: no spinner, no disabled buttons.
- Icons are served and resized by Odoo's cached image route; nothing is decoded on each page view.
- Icons are always PNG, the format browsers require for an installable app: an uploaded icon is saved as PNG, and a large favicon gets a PNG copy (Odoo stores favicons as ICO files).
- The invitation is not shown inside the website editor's preview or when the site is embedded in a frame.
- Use one app-install feature per website: if your theme has its own PWA option, switch it off on websites where this one is on.

## Technical

- Website fields `cl_pwa_enabled`, `cl_pwa_name`, `cl_pwa_short_name`, colours and `cl_pwa_icon`; stored helpers `cl_pwa_icon_size`, `cl_pwa_favicon_size` and `cl_pwa_favicon_icon` (PNG copy of the favicon).
- The install dialog is rendered inside `#wrapwrap` on the homepage and driven by the `ClPwaInstall` public widget.
- Routes `/cl_pwa/manifest.webmanifest` and `/cl_pwa/sw.js` (scope `/`); frontend widget in `web.assets_frontend`.
- Tests: `odoo -i cl_website_pwa_install --test-tags /cl_website_pwa_install`.
- Odoo 18.0 · depends on `website` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
