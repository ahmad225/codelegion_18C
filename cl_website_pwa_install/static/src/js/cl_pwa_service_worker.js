/** @odoo-module **/
// Copyright (C) Code Legion (https://thecodelegion.com). License LGPL-3.0 or later.

// Registers the app's service worker on every page of a website that offers
// app install (the server adds the manifest link only then). On a website
// where it has been switched off, the worker installed earlier is removed.

const CL_PWA_MANIFEST_URL = "/cl_pwa/manifest.webmanifest";
const CL_PWA_SW_URL = "/cl_pwa/sw.js";

function isOwnRegistration(registration) {
    const worker = registration.active || registration.waiting || registration.installing;
    return Boolean(worker) && new URL(worker.scriptURL).pathname === CL_PWA_SW_URL;
}

function syncServiceWorker() {
    if (!("serviceWorker" in navigator) || !window.isSecureContext) {
        return;
    }
    const enabled = document.querySelector(`link[rel="manifest"][href="${CL_PWA_MANIFEST_URL}"]`);
    if (enabled) {
        // A failed registration only means the site is not installable here.
        navigator.serviceWorker.register(CL_PWA_SW_URL, { scope: "/" }).catch(() => {});
        return;
    }
    navigator.serviceWorker
        .getRegistrations()
        .then((registrations) => {
            for (const registration of registrations.filter(isOwnRegistration)) {
                registration.unregister();
            }
        })
        .catch(() => {});
}

if (document.readyState === "complete") {
    syncServiceWorker();
} else {
    window.addEventListener("load", syncServiceWorker, { once: true });
}
