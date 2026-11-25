# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json

from odoo import http
from odoo.http import request

# The service worker never answers a request itself, except a page
# navigation that fails (the visitor is offline): that one gets the small
# offline page embedded below, which is stored with the worker at install.
SERVICE_WORKER_JS = """\
// Copyright (C) Code Legion (https://thecodelegion.com). License LGPL-3.0 or later.
"use strict";

const OFFLINE_PAGE = %(offline_page)s;

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.mode !== "navigate" || request.method !== "GET") {
        return; // Not handled: the browser loads it exactly as without a worker.
    }
    event.respondWith(
        fetch(request).catch(
            () =>
                new Response(OFFLINE_PAGE, {
                    status: 503,
                    statusText: "Offline",
                    headers: {
                        "Content-Type": "text/html; charset=utf-8",
                        "Cache-Control": "no-store",
                    },
                })
        )
    );
});
"""


class ClWebsitePwa(http.Controller):

    def _cl_pwa_website(self):
        website = request.website
        if not website or not website.cl_pwa_enabled:
            raise request.not_found()
        return website

    @http.route('/cl_pwa/manifest.webmanifest', type='http', auth='public',
                methods=['GET'], website=True, multilang=False, sitemap=False,
                readonly=True)
    def cl_pwa_manifest(self, **kwargs):
        website = self._cl_pwa_website()
        return request.make_json_response(website._cl_pwa_manifest(), headers={
            'Content-Type': 'application/manifest+json',
            'Cache-Control': 'no-cache',
        })

    @http.route('/cl_pwa/sw.js', type='http', auth='public', methods=['GET'],
                website=True, multilang=False, sitemap=False, readonly=True)
    def cl_pwa_service_worker(self, **kwargs):
        website = self._cl_pwa_website()
        # No editor branding: a designer may be the one installing the worker.
        offline_page = request.env['ir.qweb'].with_context(inherit_branding=False)._render(
            'cl_website_pwa_install.cl_pwa_offline_page', {
                'website': website,
                'app_name': website._cl_pwa_app_name(),
                'lang': (request.env.lang or 'en_US').replace('_', '-'),
            })
        body = SERVICE_WORKER_JS % {'offline_page': json.dumps(str(offline_page))}
        return request.make_response(body, headers=[
            ('Content-Type', 'text/javascript; charset=utf-8'),
            # Registered with scope "/" although the script lives in /cl_pwa/.
            ('Service-Worker-Allowed', '/'),
            ('Cache-Control', 'no-cache'),
        ])
