from odoo import fields, models, _

from ..services.storage_client import DEFAULT_BLOCKLIST, get_storage_client


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    s3_bucket_name = fields.Char(
        string="Bucket Name",
        config_parameter="odoo_s3_file_upload.bucket_name",
    )
    s3_region = fields.Char(
        string="Region",
        config_parameter="odoo_s3_file_upload.region",
        default="us-east-1",
    )
    s3_endpoint_url = fields.Char(
        string="Endpoint URL",
        config_parameter="odoo_s3_file_upload.endpoint_url",
        help="Leave empty for AWS S3. Set for Cloudflare R2 or other S3-compatible storage.",
    )
    s3_key_prefix = fields.Char(
        string="Key Prefix",
        config_parameter="odoo_s3_file_upload.key_prefix",
        help="Optional prefix prepended to every object key.",
    )
    s3_presigned_ttl_seconds = fields.Integer(
        string="Presigned URL TTL (seconds)",
        config_parameter="odoo_s3_file_upload.presigned_ttl_seconds",
        default=3600,
    )
    s3_use_path_style = fields.Boolean(
        string="Path-Style Addressing",
        config_parameter="odoo_s3_file_upload.use_path_style",
        help="Enable for some S3-compatible providers (e.g. MinIO, R2).",
    )
    s3_blocklist_extensions = fields.Char(
        string="Blocked Extensions",
        config_parameter="odoo_s3_file_upload.blocklist_extensions",
        default=DEFAULT_BLOCKLIST,
        help="Comma-separated list of blocked file extensions (e.g. .exe,.bat).",
    )
    s3_task_max_file_size = fields.Integer(
        string="Task Max File Size (bytes)",
        config_parameter="odoo_s3_file_upload.task_max_file_size",
        default=0,
        help="Maximum file size for project.task S3 uploads in bytes. 0 means no limit.",
    )

    def action_test_s3_connection(self):
        self.ensure_one()
        get_storage_client(self.env).test_connection()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection successful"),
                "message": _("Storage bucket is reachable."),
                "type": "success",
                "sticky": False,
            },
        }
