/** @odoo-module **/
// Copyright (C) Code Legion (https://thecodelegion.com). License LGPL-3.0 or later.

import { AccountPaymentField } from "@account/components/account_payment_field/account_payment_field";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(AccountPaymentField.prototype, {
    setup() {
        super.setup(...arguments);
        this.clDialog = useService("dialog");
    },

    /**
     * Ask before a reconciliation is removed from the payment widget.
     *
     * `moveId` is the entry on the other side (the payment, credit note...),
     * not the document on screen, so the message is asked for the record of
     * the form. Once confirmed the standard method does the work, so anything
     * else patched onto it keeps running.
     *
     * @override
     */
    async removeMoveReconcile(moveId, partialId) {
        this.popover.close();
        const { resModel, resId } = this.props.record;
        let message = _t("Are you sure you want to remove this reconciliation?");
        if (resId) {
            try {
                const result = await this.orm.call(
                    resModel,
                    "cl_unreconcile_warning_message",
                    [[resId], partialId]
                );
                message = (result && result.message) || message;
            } catch {
                // Keep the generic question: the wording must never block the action.
            }
        }
        this.clDialog.add(ConfirmationDialog, {
            title: _t("Unreconcile"),
            body: message,
            confirmLabel: _t("Unreconcile"),
            cancelLabel: _t("Keep it"),
            confirm: () => super.removeMoveReconcile(moveId, partialId),
            cancel: () => {},
        });
    },
});
