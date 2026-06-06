/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { AttachmentList } from "@mail/core/common/attachment_list";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

import { downloadS3TaskAttachment, isS3TaskAttachment } from "./s3_download";

patch(AttachmentList.prototype, {
    setup() {
        super.setup(...arguments);
        this.notificationService = useService("notification");
        this.attachmentUploadService = useService("mail.attachment_upload");
        this.fileInput = document.createElement("input");
        this.fileInput.type = "file";
        this.fileInput.classList.add("d-none");
        this.fileInput.addEventListener("change", () => this._onRetryFileSelected());
        onMounted(() => document.body.appendChild(this.fileInput));
        onWillUnmount(() => this.fileInput.remove());
        this._retryAttachment = null;
        this._retryThread = null;
        this._retryComposer = null;
    },

    /**
     * @param {import("models").Attachment} attachment
     */
    s3StatusLabel(attachment) {
        if (attachment.res_model !== "project.task" || attachment.uploading) {
            return "";
        }
        if (attachment.s3_storage_status === "pending") {
            return _t("Pending");
        }
        if (attachment.s3_storage_status === "failed") {
            return _t("Failed");
        }
        return "";
    },

    /**
     * @param {import("models").Attachment} attachment
     */
    s3StatusClass(attachment) {
        if (attachment.s3_storage_status === "failed") {
            return "text-bg-danger";
        }
        if (attachment.s3_storage_status === "pending") {
            return "text-bg-warning";
        }
        return "text-bg-secondary";
    },

    /**
     * @param {import("models").Attachment} attachment
     */
    canRetryS3(attachment) {
        return (
            attachment.id > 0 &&
            attachment.res_model === "project.task" &&
            attachment.s3_storage_status === "failed" &&
            !attachment.uploading
        );
    },

    getActions(attachment) {
        const res = super.getActions(...arguments);
        if (this.canRetryS3(attachment)) {
            res.unshift({
                label: _t("Retry upload"),
                icon: "fa fa-refresh",
                onSelect: () => this.onClickRetryS3(attachment),
            });
        }
        return res;
    },

    /**
     * @param {import("models").Attachment} attachment
     */
    async onClickRetryS3(attachment) {
        if (attachment.res_model !== "project.task" || !attachment.res_id) {
            this.notificationService.add(_t("Could not find the linked task."), {
                type: "warning",
            });
            return;
        }
        const thread = attachment.thread ||
            attachment.message?.thread ||
            this.env.thread || {
                model: "project.task",
                id: attachment.res_id,
            };
        const composer = attachment.composer;
        const result = await this.attachmentUploadService.retryS3Upload(
            attachment,
            thread,
            composer
        );
        if (result?.needsFile) {
            this._retryAttachment = attachment;
            this._retryThread = thread;
            this._retryComposer = composer;
            this.fileInput.value = "";
            this.fileInput.click();
        }
    },

    async _onRetryFileSelected() {
        const file = this.fileInput.files?.[0];
        const attachment = this._retryAttachment;
        const thread = this._retryThread;
        const composer = this._retryComposer;
        this._retryAttachment = null;
        this._retryThread = null;
        this._retryComposer = null;
        if (!file || !attachment || !thread) {
            return;
        }
        this.attachmentUploadService.rememberFailedS3File(attachment.id, file);
        await this.attachmentUploadService.retryS3Upload(attachment, thread, composer);
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
