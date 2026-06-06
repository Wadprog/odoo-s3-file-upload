/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { humanNumber } from "@web/core/utils/numbers";
import { session } from "@web/session";
import { FileUploader } from "@web/views/fields/file_handler";

Object.assign(FileUploader.props, {
    directFileUpload: { type: Boolean, optional: true },
});

function checkTaskFileSize(fileSize, notificationService) {
    const maxUploadSize = session.s3_task_max_file_upload_size || 0;
    if (!maxUploadSize) {
        return true;
    }
    if (fileSize > maxUploadSize) {
        notificationService.add(
            _t(
                "The selected file (%(size)sB) is larger than the maximum allowed file size (%(maxSize)sB).",
                { size: humanNumber(fileSize), maxSize: humanNumber(maxUploadSize) }
            ),
            { type: "danger" }
        );
        return false;
    }
    return true;
}

patch(FileUploader.prototype, {
    async onFileChange(ev) {
        if (!this.props.directFileUpload) {
            return super.onFileChange(ev);
        }

        const files = [...ev.target.files].filter((file) => this.validFileType(file));
        if (!files.length) {
            return;
        }
        const { target } = ev;
        for (const file of files) {
            if (!checkTaskFileSize(file.size, this.notification)) {
                return null;
            }
            this.state.isUploading = true;
            try {
                await this.props.onUploaded({
                    file,
                    name: file.name,
                    size: file.size,
                    type: file.type,
                });
            } finally {
                this.state.isUploading = false;
            }
        }
        target.value = null;
        if (this.props.multiUpload && this.props.onUploadComplete) {
            this.props.onUploadComplete({});
        }
    },
});
