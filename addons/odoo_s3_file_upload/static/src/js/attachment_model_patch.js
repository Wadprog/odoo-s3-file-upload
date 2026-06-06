/** @odoo-module **/

import { Attachment } from "@mail/core/common/attachment_model";
import { fields } from "@mail/core/common/record";
import { patch } from "@web/core/utils/patch";

patch(Attachment, {
    /** @type {false | "pending" | "uploaded" | "failed" | "cancelled"} */
    s3_storage_status: fields.Attr(false),
});
