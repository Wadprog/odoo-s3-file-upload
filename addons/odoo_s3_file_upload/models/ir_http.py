from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        max_size = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("odoo_s3_file_upload.task_max_file_size", "0")
        )
        result["s3_task_max_file_upload_size"] = max_size
        return result
