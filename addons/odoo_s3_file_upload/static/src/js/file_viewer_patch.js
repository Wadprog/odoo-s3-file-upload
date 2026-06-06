/** @odoo-module **/

import { FileViewer } from "@web/core/file_viewer/file_viewer";
import { download } from "@web/core/network/download";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

import { downloadS3TaskAttachment, isS3TaskAttachment } from "./s3_download";

patch(FileViewer.prototype, {
    setup() {
        super.setup(...arguments);
        this.notificationService = useService("notification");
    },

    async onClickDownload() {
        const file = this.state.file;
        if (isS3TaskAttachment(file)) {
            await downloadS3TaskAttachment(file, this.notificationService);
            return;
        }
        await download({
            data: {},
            url: file.downloadUrl,
        });
    },
});
