import os
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services.storage_client import DEFAULT_BLOCKLIST, get_storage_client

S3_STATUS_PENDING = "pending"
S3_STATUS_UPLOADED = "uploaded"
S3_STATUS_FAILED = "failed"
S3_STATUS_CANCELLED = "cancelled"


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    s3_storage_status = fields.Selection(
        selection=[
            (S3_STATUS_PENDING, "Pending"),
            (S3_STATUS_UPLOADED, "Uploaded"),
            (S3_STATUS_FAILED, "Failed"),
            (S3_STATUS_CANCELLED, "Cancelled"),
        ],
        string="S3 Storage Status",
        copy=False,
    )
    s3_bucket = fields.Char(string="S3 Bucket", copy=False)
    s3_key = fields.Char(string="S3 Object Key", copy=False, index=True)
    s3_upload_id = fields.Char(string="S3 Multipart Upload ID", copy=False)
    s3_etag = fields.Char(string="S3 ETag", copy=False)
    s3_file_size = fields.Integer(string="S3 File Size", copy=False)
    storage_provider = fields.Selection(
        selection=[("s3", "AWS S3"), ("r2", "Cloudflare R2")],
        string="Storage Provider",
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Guards
    # -------------------------------------------------------------------------

    @staticmethod
    def _vals_has_binary_payload(vals):
        return bool(vals.get("datas") or vals.get("raw"))

    def _get_blocklist(self):
        client = get_storage_client(self.env)
        raw = client.blocklist_extensions or DEFAULT_BLOCKLIST
        return {ext.strip().lower() for ext in raw.split(",") if ext.strip()}

    def _check_blocklist_filename(self, filename):
        _, ext = os.path.splitext(filename or "")
        if ext.lower() in self._get_blocklist():
            raise UserError(
                _("File type %(ext)s is not allowed for task attachments.", ext=ext)
            )

    def _guard_project_task_create(self, vals):
        if vals.get("res_model") != "project.task":
            return

        if self.env.context.get("s3_upload_allowed"):
            if vals.get("name"):
                self._check_blocklist_filename(vals["name"])
            return

        if self._vals_has_binary_payload(vals):
            raise UserError(
                _(
                    "Local file uploads are not allowed on project tasks. "
                    "Use the S3 upload flow instead."
                )
            )

        raise UserError(
            _("Attachments on project tasks must be created through the S3 upload flow.")
        )

    def _guard_project_task_write(self, vals):
        if self.env.context.get("s3_upload_allowed"):
            if vals.get("name"):
                self._check_blocklist_filename(vals["name"])
            return

        if not self._vals_has_binary_payload(vals):
            return

        for attachment in self:
            if attachment.res_model == "project.task":
                raise UserError(
                    _(
                        "Local file uploads are not allowed on project tasks. "
                        "Use the S3 upload flow instead."
                    )
                )

    # -------------------------------------------------------------------------
    # Key generation & lifecycle
    # -------------------------------------------------------------------------

    @api.model
    def _detect_storage_provider(self):
        client = get_storage_client(self.env)
        endpoint = client.endpoint_url or ""
        if "r2.cloudflarestorage.com" in endpoint:
            return "r2"
        return "s3"

    @api.model
    def _generate_s3_key(self, task, filename):
        safe_name = os.path.basename(filename or "file")
        unique = uuid.uuid4().hex
        return f"projects/{task.project_id.id}/tasks/{task.id}/{unique}_{safe_name}"

    @api.model
    def s3_create_pending(self, task_id, filename, mimetype, file_size):
        """Create a draft task attachment with a reserved S3 object key."""
        task = self.env["project.task"].browse(task_id).exists()
        if not task:
            raise UserError(_("Task %s does not exist.", task_id))

        self._check_blocklist_filename(filename)
        client = get_storage_client(self.env)
        s3_key = self._generate_s3_key(task, filename)

        return self.with_context(s3_upload_allowed=True).create(
            {
                "name": filename,
                "res_model": "project.task",
                "res_id": task.id,
                "mimetype": mimetype,
                "s3_storage_status": S3_STATUS_PENDING,
                "s3_bucket": client.bucket,
                "s3_key": s3_key,
                "s3_file_size": file_size,
                "storage_provider": self._detect_storage_provider(),
                "type": "binary",
                "datas": False,
            }
        )

    def s3_mark_uploaded(self, etag=None):
        self.ensure_one()
        vals = {
            "s3_storage_status": S3_STATUS_UPLOADED,
            "s3_upload_id": False,
        }
        if etag:
            vals["s3_etag"] = etag
        self.with_context(s3_upload_allowed=True).write(vals)

    def s3_mark_failed(self):
        self.ensure_one()
        self.with_context(s3_upload_allowed=True).write(
            {"s3_storage_status": S3_STATUS_FAILED}
        )

    def s3_cancel(self):
        self.ensure_one()
        if self.s3_upload_id and self.s3_key:
            client = get_storage_client(self.env)
            client.abort_multipart(self.s3_key, self.s3_upload_id)
        self.with_context(s3_upload_allowed=True).unlink()

    def s3_resolve_retry_key(self):
        """Reuse key when no object exists; rotate when a partial object exists."""
        self.ensure_one()
        if not self.s3_key:
            raise UserError(_("Attachment has no S3 key to retry."))

        client = get_storage_client(self.env)
        if client.head_object(self.s3_key) is None:
            return self.s3_key

        task = self.env["project.task"].browse(self.res_id).exists()
        if not task:
            raise UserError(_("Linked task no longer exists."))

        new_key = self._generate_s3_key(task, self.name)
        self.with_context(s3_upload_allowed=True).write(
            {
                "s3_key": new_key,
                "s3_upload_id": False,
                "s3_etag": False,
                "s3_storage_status": S3_STATUS_PENDING,
            }
        )
        return new_key

    # -------------------------------------------------------------------------
    # ORM overrides
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._guard_project_task_create(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._guard_project_task_write(vals)
        return super().write(vals)
