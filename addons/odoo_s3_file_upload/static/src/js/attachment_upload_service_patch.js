/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { Deferred } from "@web/core/utils/concurrency";
import { AttachmentUploadService } from "@mail/core/common/attachment_upload_service";

import { uploadTaskFileToS3 } from "./s3_multipart_upload";

patch(AttachmentUploadService.prototype, {
    setup() {
        super.setup(...arguments);
        /** @type {Map<number, {abortController: AbortController, attachmentId?: number}>} */
        this._s3UploadsByTmpId = new Map();
    },

    async upload(thread, composer, file, options) {
        if (thread.model === "project.task") {
            return this._uploadProjectTaskS3(thread, composer, file);
        }
        return super.upload(thread, composer, file, options);
    },

    async unlink(attachment) {
        const s3Upload = this._s3UploadsByTmpId.get(attachment.id);
        if (s3Upload) {
            s3Upload.abortController.abort();
            if (s3Upload.attachmentId) {
                await rpc("/odoo_s3_file_upload/cancel", {
                    attachment_id: s3Upload.attachmentId,
                });
            }
            this._cleanupS3Upload(attachment.id);
            return;
        }
        return super.unlink(...arguments);
    },

    _cleanupS3Upload(tmpId) {
        this._s3UploadsByTmpId.delete(tmpId);
        this.store["ir.attachment"].get(tmpId)?.remove();
    },

    async _uploadProjectTaskS3(thread, composer, file) {
        const tmpId = this.nextId--;
        const tmpURL = URL.createObjectURL(file);
        const def = new Deferred();
        const abortController = new AbortController();

        this._s3UploadsByTmpId.set(tmpId, { abortController });
        this.targetsByTmpId.set(tmpId, { composer, thread });
        this.uploadingAttachmentIds.add(tmpId);

        const attachment = this.store["ir.attachment"].insert({
            id: tmpId,
            mimetype: file.type,
            name: file.name,
            resModel: thread.model,
            thread,
            extension: file.name.includes(".") ? file.name.split(".").pop() : "",
            uploading: true,
            tmpUrl: tmpURL,
        });
        composer?.attachments.push(attachment);

        const closeNotification = this.notificationService.add(
            _t("Uploading %(file)s...", { file: file.name }),
            { sticky: true, type: "info" }
        );

        try {
            const { attachmentId } = await uploadTaskFileToS3({
                taskId: thread.id,
                file,
                signal: abortController.signal,
            });

            const s3Upload = this._s3UploadsByTmpId.get(tmpId);
            if (s3Upload) {
                s3Upload.attachmentId = attachmentId;
            }

            const uploaded = this.store["ir.attachment"].insert({
                id: attachmentId,
                mimetype: file.type,
                name: file.name,
                resModel: thread.model,
                resId: thread.id,
                thread,
                extension: file.name.includes(".") ? file.name.split(".").pop() : "",
                uploading: false,
            });

            if (composer) {
                const index = composer.attachments.findIndex(({ id }) => id === tmpId);
                if (index >= 0) {
                    composer.attachments[index] = uploaded;
                } else {
                    composer.attachments.push(uploaded);
                }
            }

            this.notificationService.add(
                _t("Uploaded %(file)s", { file: file.name }),
                { type: "success" }
            );
            this._fileUploadBus.trigger("UPLOAD", thread);
            def.resolve(uploaded);
        } catch (error) {
            if (error.name === "AbortError") {
                this.notificationService.add(_t("Upload cancelled"), { type: "warning" });
            } else {
                this.notificationService.add(
                    _t("Upload failed for %(file)s. Please try again.", { file: file.name }),
                    { type: "danger" }
                );
            }
            def.resolve();
        } finally {
            if (typeof closeNotification === "function") {
                closeNotification();
            }
            URL.revokeObjectURL(tmpURL);
            this._cleanupS3Upload(tmpId);
            this.targetsByTmpId.delete(tmpId);
            this.uploadingAttachmentIds.delete(tmpId);
        }

        return def;
    },
});
