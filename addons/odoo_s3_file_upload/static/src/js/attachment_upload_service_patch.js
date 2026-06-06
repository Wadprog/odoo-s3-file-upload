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
        /** @type {Map<number, File>} */
        this._s3FailedFiles = new Map();
    },

    async upload(thread, composer, file, options) {
        if (thread.model === "project.task") {
            return this._uploadProjectTaskS3(thread, composer, file);
        }
        return super.upload(thread, composer, file, options);
    },

    /**
     * Retry a failed S3 task upload when the original File is still available.
     * @returns {Promise<import("@web/core/utils/concurrency").Deferred|{needsFile: true}>}
     */
    async retryS3Upload(attachment, thread, composer) {
        const file = this._s3FailedFiles.get(attachment.id);
        if (!file) {
            return { needsFile: true };
        }
        return this._uploadProjectTaskS3(thread, composer, file, {
            attachmentId: attachment.id,
            replaceAttachment: attachment,
        });
    },

    rememberFailedS3File(attachmentId, file) {
        this._s3FailedFiles.set(attachmentId, file);
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
        if (attachment.id > 0) {
            this._s3FailedFiles.delete(attachment.id);
        }
        return super.unlink(...arguments);
    },

    _cleanupS3Upload(tmpId) {
        this._s3UploadsByTmpId.delete(tmpId);
        this.store["ir.attachment"].get(tmpId)?.remove();
    },

    /**
     * @param {Object} [options]
     * @param {number} [options.attachmentId]
     * @param {import("models").Attachment} [options.replaceAttachment]
     */
    async _uploadProjectTaskS3(thread, composer, file, options = {}) {
        const { attachmentId, replaceAttachment } = options;
        const isRetry = Boolean(attachmentId);
        const tmpId = isRetry ? attachmentId : this.nextId--;
        const tmpURL = isRetry ? undefined : URL.createObjectURL(file);
        const def = new Deferred();
        const abortController = new AbortController();

        if (!isRetry) {
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
        } else if (replaceAttachment) {
            this.store["ir.attachment"].insert({
                id: attachmentId,
                uploading: true,
                s3_storage_status: "pending",
            });
            this._s3UploadsByTmpId.set(tmpId, { abortController, attachmentId });
            this.uploadingAttachmentIds.add(tmpId);
        }

        let uploadError = null;
        let closeNotification = this.notificationService.add(
            _t("Uploading %(file)s… 0%%", { file: file.name }),
            { sticky: true, type: "info" }
        );
        let lastProgress = -1;

        const onProgress = (pct) => {
            if (pct - lastProgress < 5 && pct < 100) {
                return;
            }
            lastProgress = pct;
            if (typeof closeNotification === "function") {
                closeNotification();
            }
            closeNotification = this.notificationService.add(
                _t("Uploading %(file)s… %(pct)s%%", { file: file.name, pct }),
                { sticky: true, type: "info" }
            );
        };

        try {
            const { attachmentId: resolvedId } = await uploadTaskFileToS3({
                taskId: thread.id,
                file,
                attachmentId,
                signal: abortController.signal,
                onProgress,
            });

            this._s3FailedFiles.delete(resolvedId);

            const s3Upload = this._s3UploadsByTmpId.get(tmpId);
            if (s3Upload) {
                s3Upload.attachmentId = resolvedId;
            }

            const uploaded = this.store["ir.attachment"].insert({
                id: resolvedId,
                mimetype: file.type,
                name: file.name,
                resModel: thread.model,
                resId: thread.id,
                thread,
                extension: file.name.includes(".") ? file.name.split(".").pop() : "",
                uploading: false,
                s3_storage_status: "uploaded",
            });

            if (composer) {
                const index = composer.attachments.findIndex(
                    ({ id }) => id === tmpId || id === resolvedId
                );
                if (index >= 0) {
                    composer.attachments[index] = uploaded;
                } else {
                    composer.attachments.push(uploaded);
                }
            }

            this.notificationService.add(_t("Uploaded %(file)s", { file: file.name }), {
                type: "success",
            });
            this._fileUploadBus.trigger("UPLOAD", thread);
            def.resolve(uploaded);
        } catch (error) {
            uploadError = error;
            const failedId = error.s3AttachmentId || attachmentId;
            if (error.name === "AbortError") {
                this.notificationService.add(_t("Upload cancelled"), { type: "warning" });
            } else {
                const isCorsOrNetwork =
                    error.message === "Failed to fetch" || error.name === "TypeError";
                this.notificationService.add(
                    isCorsOrNetwork
                        ? _t(
                              "Upload failed for %(file)s: browser could not reach storage. Configure CORS on your S3/R2 bucket to allow PUT from this Odoo origin.",
                              { file: file.name }
                          )
                        : _t("Upload failed for %(file)s: %(reason)s", {
                              file: file.name,
                              reason: error.message,
                          }),
                    { type: "danger", sticky: isCorsOrNetwork }
                );
                if (failedId) {
                    this._s3FailedFiles.set(failedId, file);
                    const failed = this.store["ir.attachment"].insert({
                        id: failedId,
                        mimetype: file.type,
                        name: file.name,
                        resModel: thread.model,
                        resId: thread.id,
                        thread,
                        extension: file.name.includes(".") ? file.name.split(".").pop() : "",
                        uploading: false,
                        s3_storage_status: "failed",
                    });
                    if (composer) {
                        const index = composer.attachments.findIndex(
                            ({ id }) => id === tmpId || id === failedId
                        );
                        if (index >= 0) {
                            composer.attachments[index] = failed;
                        } else {
                            composer.attachments.push(failed);
                        }
                    }
                }
            }
            def.resolve();
        } finally {
            if (typeof closeNotification === "function") {
                closeNotification();
            }
            if (tmpURL) {
                URL.revokeObjectURL(tmpURL);
            }
            if (!isRetry) {
                this._cleanupS3Upload(tmpId);
            } else {
                this._s3UploadsByTmpId.delete(tmpId);
            }
            this.targetsByTmpId.delete(tmpId);
            this.uploadingAttachmentIds.delete(tmpId);
            if (isRetry && uploadError?.name === "AbortError" && attachmentId) {
                this.store["ir.attachment"].insert({
                    id: attachmentId,
                    uploading: false,
                    s3_storage_status: "failed",
                });
            }
        }

        return def;
    },
});
