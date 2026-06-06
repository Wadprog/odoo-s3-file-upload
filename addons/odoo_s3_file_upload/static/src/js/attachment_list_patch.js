/** @odoo-module **/

import { AttachmentList } from "@mail/core/common/attachment_list";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

import { downloadS3TaskAttachment, isS3TaskAttachment } from "./s3_download";

patch(AttachmentList.prototype, {
    setup() {
        super.setup(...arguments);
        this.notificationService = useService("notification");
    },

    /**
     * @param {import("models").Attachment} attachment
     */
    async onClickDownload(attachment) {
        if (isS3TaskAttachment(attachment)) {
            await downloadS3TaskAttachment(attachment, this.notificationService);
            return;
        }
        return super.onClickDownload(...arguments);
    },
});
