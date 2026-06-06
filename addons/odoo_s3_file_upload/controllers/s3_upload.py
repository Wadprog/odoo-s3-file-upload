import logging

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request

from ..const import DEFAULT_PART_SIZE

_logger = logging.getLogger(__name__)


class S3UploadController(http.Controller):
    def _get_task_attachment(self, attachment_id, access_mode="write"):
        attachment = request.env["ir.attachment"].browse(attachment_id).exists()
        if not attachment:
            raise UserError(_("Attachment not found."))
        attachment.check_access(access_mode)
        if attachment.res_model != "project.task":
            raise UserError(_("Attachment is not linked to a project task."))
        return attachment

    @http.route("/odoo_s3_file_upload/create_pending", type="jsonrpc", auth="user")
    def create_pending(self, task_id, filename, mimetype, file_size):
        task = request.env["project.task"].browse(task_id).exists()
        if not task:
            raise UserError(_("Task not found."))
        task.check_access("write")

        attachment = request.env["ir.attachment"].s3_create_pending(
            task_id, filename, mimetype, file_size
        )
        return {
            "attachment_id": attachment.id,
            "s3_key": attachment.s3_key,
            "part_size": DEFAULT_PART_SIZE,
        }

    @http.route("/odoo_s3_file_upload/init", type="jsonrpc", auth="user")
    def init_upload(self, attachment_id):
        attachment = self._get_task_attachment(attachment_id)
        upload_id = attachment.s3_init_multipart()
        return {"upload_id": upload_id}

    @http.route("/odoo_s3_file_upload/presign_part", type="jsonrpc", auth="user")
    def presign_part(self, attachment_id, upload_id, part_number):
        attachment = self._get_task_attachment(attachment_id)
        url = attachment.s3_presign_part(upload_id, part_number)
        return {"presigned_url": url}

    @http.route("/odoo_s3_file_upload/complete", type="jsonrpc", auth="user")
    def complete_upload(self, attachment_id, upload_id, parts):
        attachment = self._get_task_attachment(attachment_id)
        result = attachment.s3_complete_multipart(upload_id, parts)
        return {"etag": result.get("ETag")}

    @http.route("/odoo_s3_file_upload/finalize", type="jsonrpc", auth="user")
    def finalize_upload(self, attachment_id):
        attachment = self._get_task_attachment(attachment_id)
        attachment.s3_finalize()
        return {"status": attachment.s3_storage_status}

    @http.route("/odoo_s3_file_upload/fail", type="jsonrpc", auth="user")
    def fail_upload(self, attachment_id, reason=None):
        attachment = self._get_task_attachment(attachment_id)
        if reason:
            _logger.error(
                "S3 upload failed for attachment %s: %s", attachment.id, reason
            )
        attachment.s3_mark_failed()
        return {"status": attachment.s3_storage_status}

    @http.route("/odoo_s3_file_upload/cancel", type="jsonrpc", auth="user")
    def cancel_upload(self, attachment_id):
        attachment = self._get_task_attachment(attachment_id)
        attachment.s3_cancel()
        return {"cancelled": True}

    @http.route("/odoo_s3_file_upload/abort", type="jsonrpc", auth="user")
    def abort_upload(self, attachment_id):
        attachment = self._get_task_attachment(attachment_id)
        attachment.s3_abort_multipart()
        return {"aborted": True}

    @http.route("/odoo_s3_file_upload/get_download_url", type="jsonrpc", auth="user")
    def get_download_url(self, attachment_id):
        attachment = self._get_task_attachment(attachment_id, access_mode="read")
        url = attachment.s3_get_download_url()
        ttl = int(
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("odoo_s3_file_upload.presigned_ttl_seconds", "3600")
        )
        return {"download_url": url, "ttl_seconds": ttl}

    @http.route("/odoo_s3_file_upload/download/<int:attachment_id>", type="http", auth="user")
    def download_redirect(self, attachment_id):
        attachment = request.env["ir.attachment"].browse(attachment_id).exists()
        if not attachment:
            raise UserError(_("Attachment not found."))
        url = attachment.s3_get_download_url()
        return request.redirect(url, code=302, local=False)
