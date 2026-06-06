/** @odoo-module **/

import { AttachmentUploader } from "@mail/core/common/attachment_uploader_hook";
import { patch } from "@web/core/utils/patch";

patch(AttachmentUploader.prototype, {
    uploadData({ data, name, type, file }, options) {
        if (file instanceof File) {
            return this.uploadFile(file, options);
        }
        return super.uploadData(...arguments);
    },
});
