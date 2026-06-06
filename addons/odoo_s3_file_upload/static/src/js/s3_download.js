/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

/**
 * @param {import("models").Attachment} attachment
 * @returns {boolean}
 */
export function isS3TaskAttachment(attachment) {
    return (
        attachment.id > 0 &&
        !attachment.uploading &&
        attachment.res_model === "project.task"
    );
}

/**
 * @param {import("models").Attachment} attachment
 * @param {import("@web/core/notifications/notification_service").NotificationService} notificationService
 */
export async function downloadS3TaskAttachment(attachment, notificationService) {
    const closeNotification = notificationService.add(
        _t("Downloading %(file)s...", { file: attachment.name }),
        { sticky: true, type: "info" }
    );

    try {
        const { download_url: downloadUrl } = await rpc("/odoo_s3_file_upload/get_download_url", {
            attachment_id: attachment.id,
        });

        const response = await fetch(downloadUrl);
        if (!response.ok) {
            throw new Error(`Download failed (${response.status})`);
        }

        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = blobUrl;
        anchor.download = attachment.name || "download";
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(blobUrl);

        notificationService.add(
            _t("Downloaded %(file)s", { file: attachment.name }),
            { type: "success" }
        );
    } catch (error) {
        const isCorsOrNetwork =
            error.message === "Failed to fetch" || error.name === "TypeError";
        notificationService.add(
            isCorsOrNetwork
                ? _t(
                      "Download failed for %(file)s: browser could not reach storage. Configure CORS on your S3/R2 bucket to allow GET from this Odoo origin.",
                      { file: attachment.name }
                  )
                : _t("Download failed for %(file)s: %(reason)s", {
                      file: attachment.name,
                      reason: error.message,
                  }),
            { type: "danger", sticky: isCorsOrNetwork }
        );
    } finally {
        if (typeof closeNotification === "function") {
            closeNotification();
        }
    }
}
