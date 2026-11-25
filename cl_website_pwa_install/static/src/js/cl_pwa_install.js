/** @odoo-module **/
// Copyright (C) Code Legion (https://thecodelegion.com). License LGPL-3.0 or later.

import publicWidget from "@web/legacy/js/public/public_widget";
import { getTabableElements } from "@web/core/utils/ui";

// "Not now" lasts for the visit, "Don't show again" for the device.
const LATER_KEY = "cl_pwa_install_later";
const NEVER_KEY = "cl_pwa_install_never";
// Set by the inline script of the page head when the browser fires
// "beforeinstallprompt" (Chrome, Edge, Android).
const PROMPT_EVENT = "cl-pwa-installprompt";

function getStorage(name) {
    try {
        return window[name] || null;
    } catch {
        return null; // Storage blocked (privacy settings, sandboxed frame...).
    }
}

function hasFlag(storageName, key) {
    try {
        return getStorage(storageName)?.getItem(key) === "1";
    } catch {
        return false;
    }
}

function setFlag(storageName, key) {
    try {
        getStorage(storageName)?.setItem(key, "1");
    } catch {
        // Storage full or blocked: the dialog simply comes back next time.
    }
}

function isDismissed() {
    return hasFlag("sessionStorage", LATER_KEY) || hasFlag("localStorage", NEVER_KEY);
}

function isStandalone() {
    return (
        window.navigator.standalone === true ||
        Boolean(window.matchMedia?.("(display-mode: standalone)")?.matches)
    );
}

/**
 * A page shown inside a frame (the website editor's preview, or the site
 * embedded in another one) cannot be installed from there.
 */
function isFramed() {
    try {
        return window.self !== window.top;
    } catch {
        return true;
    }
}

/**
 * Browsers without an install event, but with a manual way to add the site:
 * Safari on iPhone / iPad ("ios") and Safari 17+ on a Mac ("macos").
 * Any other browser gets nothing.
 */
function getManualInstallVariant() {
    if (!/Apple/.test(navigator.vendor || "")) {
        return null;
    }
    const ua = navigator.userAgent;
    // iPadOS reports itself as a Mac: tell it apart by its touch screen.
    const isIOS =
        /iPhone|iPad|iPod/.test(ua) ||
        (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
    if (isIOS) {
        // Other iOS browsers (Chrome, Firefox, Edge...) use WebKit too.
        return /CriOS|FxiOS|EdgiOS|OPiOS|GSA\/|DuckDuckGo|YaBrowser/.test(ua) ? null : "ios";
    }
    const version = /Version\/(\d+)/.exec(ua);
    if (/Macintosh/.test(ua) && / Safari\//.test(ua) && version && Number(version[1]) >= 17) {
        return "macos";
    }
    return null;
}

publicWidget.registry.ClPwaInstall = publicWidget.Widget.extend({
    selector: "#cl_pwa_install",
    disabledInEditableMode: true,
    events: {
        "click [data-cl-pwa-action='install']": "_onInstallClick",
        "click [data-cl-pwa-action='later']": "_onLaterClick",
        "click [data-cl-pwa-action='never']": "_onNeverClick",
        keydown: "_onKeydown",
    },

    /**
     * @override
     */
    start() {
        this.dialogEl = this.el.querySelector(".cl-pwa-install-dialog");
        this._onPromptAvailable = this._onPromptAvailable.bind(this);
        this._onAppInstalled = this._onAppInstalled.bind(this);
        if (!isFramed() && !isStandalone() && !isDismissed()) {
            window.addEventListener("appinstalled", this._onAppInstalled);
            if (window.clPwaInstallPrompt) {
                this._show("prompt");
            } else {
                const manualVariant = getManualInstallVariant();
                if (manualVariant) {
                    this._show(manualVariant);
                } else {
                    window.addEventListener(PROMPT_EVENT, this._onPromptAvailable);
                }
            }
        }
        return this._super(...arguments);
    },
    /**
     * @override
     */
    destroy() {
        window.removeEventListener(PROMPT_EVENT, this._onPromptAvailable);
        window.removeEventListener("appinstalled", this._onAppInstalled);
        this._hide({ restoreFocus: false });
        this._super(...arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _show(variant) {
        for (const el of this.el.querySelectorAll("[data-cl-pwa-variant]")) {
            el.hidden = el.dataset.clPwaVariant !== variant;
        }
        this.previousFocusEl = document.activeElement;
        this.el.hidden = false;
        const installButton = this.el.querySelector("[data-cl-pwa-action='install']");
        (variant === "prompt" ? installButton : this.dialogEl).focus();
    },
    _hide({ restoreFocus = true } = {}) {
        if (!this.el || this.el.hidden) {
            return;
        }
        this.el.hidden = true;
        if (restoreFocus && this.previousFocusEl?.isConnected) {
            this.previousFocusEl.focus();
        }
        this.previousFocusEl = null;
    },
    _dismissForVisit() {
        setFlag("sessionStorage", LATER_KEY);
        this._hide();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onPromptAvailable() {
        window.removeEventListener(PROMPT_EVENT, this._onPromptAvailable);
        if (window.clPwaInstallPrompt && !isDismissed()) {
            this._show("prompt");
        }
    },
    async _onInstallClick() {
        const promptEvent = window.clPwaInstallPrompt;
        // The browser's install event can only be used once.
        window.clPwaInstallPrompt = null;
        this._hide();
        if (!promptEvent) {
            return;
        }
        try {
            // Called before any await, while the click still counts as a user gesture.
            await promptEvent.prompt();
            const choice = await promptEvent.userChoice;
            if (choice.outcome !== "accepted") {
                setFlag("sessionStorage", LATER_KEY);
            }
        } catch {
            // The browser refused to show its dialog: nothing more to do.
        }
    },
    _onLaterClick() {
        this._dismissForVisit();
    },
    _onNeverClick() {
        setFlag("localStorage", NEVER_KEY);
        this._hide();
    },
    _onAppInstalled() {
        setFlag("localStorage", NEVER_KEY);
        this._hide({ restoreFocus: false });
    },
    /**
     * Escape closes the dialog; Tab and Shift+Tab stay inside it.
     */
    _onKeydown(ev) {
        if (this.el.hidden) {
            return;
        }
        if (ev.key === "Escape") {
            ev.preventDefault();
            this._dismissForVisit();
            return;
        }
        if (ev.key !== "Tab") {
            return;
        }
        const tabbables = getTabableElements(this.dialogEl);
        if (!tabbables.length) {
            ev.preventDefault();
            return;
        }
        const first = tabbables[0];
        const last = tabbables[tabbables.length - 1];
        const active = document.activeElement;
        if (ev.shiftKey && (active === first || active === this.dialogEl)) {
            ev.preventDefault();
            last.focus();
        } else if (!ev.shiftKey && active === last) {
            ev.preventDefault();
            first.focus();
        }
    },
});

export default publicWidget.registry.ClPwaInstall;
