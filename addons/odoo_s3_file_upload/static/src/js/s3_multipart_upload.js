/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/**
 * Upload a file to S3/R2 via Odoo presigned multipart routes.
 * @param {Object} params
 * @param {number} params.taskId
 * @param {File} params.file
 * @param {AbortSignal} [params.signal]
 * @param {(progress: number) => void} [params.onProgress]
 * @returns {Promise<{attachmentId: number, s3Key: string}>}
 */
export async function uploadTaskFileToS3({ taskId, file, signal, onProgress }) {
    const mimetype = file.type || "application/octet-stream";
    const pending = await rpc("/odoo_s3_file_upload/create_pending", {
        task_id: taskId,
        filename: file.name,
        mimetype,
        file_size: file.size,
    });

    const attachmentId = pending.attachment_id;
    const partSize = pending.part_size;
    let uploadId;

    try {
        const initResult = await rpc("/odoo_s3_file_upload/init", {
            attachment_id: attachmentId,
        });
        uploadId = initResult.upload_id;

        const parts = [];
        let partNumber = 1;
        const chunks =
            file.size === 0
                ? [file.slice(0, 0)]
                : Array.from(
                      { length: Math.ceil(file.size / partSize) },
                      (_, index) => {
                          const start = index * partSize;
                          return file.slice(start, Math.min(start + partSize, file.size));
                      }
                  );

        for (const chunk of chunks) {
            if (signal?.aborted) {
                throw new DOMException("Upload cancelled", "AbortError");
            }

            const { presigned_url: presignedUrl } = await rpc(
                "/odoo_s3_file_upload/presign_part",
                {
                    attachment_id: attachmentId,
                    upload_id: uploadId,
                    part_number: partNumber,
                }
            );

            const response = await fetch(presignedUrl, {
                method: "PUT",
                body: chunk,
                signal,
            });

            if (!response.ok) {
                throw new Error(`Storage upload failed (${response.status})`);
            }

            const etag = response.headers.get("ETag");
            if (!etag) {
                throw new Error("Storage upload did not return an ETag");
            }

            parts.push({ part_number: partNumber, etag });
            if (onProgress) {
                onProgress(Math.round((partNumber / chunks.length) * 100));
            }
            partNumber += 1;
        }

        await rpc("/odoo_s3_file_upload/complete", {
            attachment_id: attachmentId,
            upload_id: uploadId,
            parts,
        });
        await rpc("/odoo_s3_file_upload/finalize", { attachment_id: attachmentId });

        return { attachmentId, s3Key: pending.s3_key };
    } catch (error) {
        if (error.name === "AbortError") {
            await rpc("/odoo_s3_file_upload/cancel", {
                attachment_id: attachmentId,
            });
        } else {
            await rpc("/odoo_s3_file_upload/fail", {
                attachment_id: attachmentId,
                reason: String(error),
            });
        }
        throw error;
    }
}
