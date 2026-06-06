/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

const DEFAULT_PART_SIZE = 64 * 1024 * 1024;
const MAX_PART_PUT_ATTEMPTS = 3;

/**
 * @param {Object} params
 * @param {number} params.attachmentId
 * @param {string} params.uploadId
 * @param {number} params.partNumber
 * @param {Blob} params.chunk
 * @param {AbortSignal} [params.signal]
 */
async function putPartWithPresignRetry({ attachmentId, uploadId, partNumber, chunk, signal }) {
    let lastError;
    for (let attempt = 0; attempt < MAX_PART_PUT_ATTEMPTS; attempt++) {
        const { presigned_url: presignedUrl } = await rpc("/odoo_s3_file_upload/presign_part", {
            attachment_id: attachmentId,
            upload_id: uploadId,
            part_number: partNumber,
        });

        const response = await fetch(presignedUrl, {
            method: "PUT",
            body: chunk,
            signal,
        });

        if (response.ok) {
            const etag = response.headers.get("ETag");
            if (!etag) {
                throw new Error("Storage upload did not return an ETag");
            }
            return etag;
        }

        if (response.status === 403 || response.status === 400) {
            lastError = new Error(`Storage upload failed (${response.status})`);
            continue;
        }

        throw new Error(`Storage upload failed (${response.status})`);
    }
    throw lastError || new Error("Storage upload failed: presigned URL expired");
}

/**
 * Upload a file to S3/R2 via Odoo presigned multipart routes.
 * @param {Object} params
 * @param {number} params.taskId
 * @param {File} params.file
 * @param {number} [params.attachmentId] existing draft for retry
 * @param {AbortSignal} [params.signal]
 * @param {(progress: number) => void} [params.onProgress]
 * @returns {Promise<{attachmentId: number, s3Key: string}>}
 */
export async function uploadTaskFileToS3({ taskId, file, attachmentId, signal, onProgress }) {
    const mimetype = file.type || "application/octet-stream";
    let resolvedAttachmentId = attachmentId;
    let s3Key;
    let partSize = DEFAULT_PART_SIZE;

    if (!resolvedAttachmentId) {
        const pending = await rpc("/odoo_s3_file_upload/create_pending", {
            task_id: taskId,
            filename: file.name,
            mimetype,
            file_size: file.size,
        });
        resolvedAttachmentId = pending.attachment_id;
        s3Key = pending.s3_key;
        partSize = pending.part_size;
    }

    let uploadId;

    try {
        const initResult = await rpc("/odoo_s3_file_upload/init", {
            attachment_id: resolvedAttachmentId,
        });
        uploadId = initResult.upload_id;
        partSize = initResult.part_size || partSize;

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

            const etag = await putPartWithPresignRetry({
                attachmentId: resolvedAttachmentId,
                uploadId,
                partNumber,
                chunk,
                signal,
            });

            parts.push({ part_number: partNumber, etag });
            if (onProgress) {
                onProgress(Math.round((partNumber / chunks.length) * 100));
            }
            partNumber += 1;
        }

        await rpc("/odoo_s3_file_upload/complete", {
            attachment_id: resolvedAttachmentId,
            upload_id: uploadId,
            parts,
        });
        await rpc("/odoo_s3_file_upload/finalize", { attachment_id: resolvedAttachmentId });

        return { attachmentId: resolvedAttachmentId, s3Key };
    } catch (error) {
        error.s3AttachmentId = resolvedAttachmentId;
        if (error.name === "AbortError") {
            await rpc("/odoo_s3_file_upload/cancel", {
                attachment_id: resolvedAttachmentId,
            });
        } else {
            await rpc("/odoo_s3_file_upload/fail", {
                attachment_id: resolvedAttachmentId,
                reason: String(error),
            });
        }
        throw error;
    }
}
