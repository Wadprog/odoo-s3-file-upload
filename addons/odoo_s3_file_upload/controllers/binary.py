from odoo import http
from odoo.http import request

from odoo.addons.web.controllers.binary import Binary


class S3BinaryController(Binary):
    """Redirect standard attachment downloads to presigned S3 URLs."""

    @http.route(
        [
            "/web/content",
            "/web/content/<string:xmlid>",
            "/web/content/<string:xmlid>/<string:filename>",
            "/web/content/<int:id>",
            "/web/content/<int:id>/<string:filename>",
            "/web/content/<string:model>/<int:id>/<string:field>",
            "/web/content/<string:model>/<int:id>/<string:field>/<string:filename>",
        ],
        type="http",
        auth="public",
        readonly=True,
    )
    def content_common(
        self,
        xmlid=None,
        model="ir.attachment",
        id=None,
        field="raw",
        filename=None,
        download=None,
        access_token=None,
        nocache=False,
        **kwargs,
    ):
        if model == "ir.attachment" and id:
            attachment = request.env["ir.attachment"].browse(int(id)).exists()
            if (
                attachment.s3_storage_status == "uploaded"
                and attachment.s3_key
                and attachment.res_model == "project.task"
            ):
                attachment.check_access("read")
                return request.redirect(
                    attachment.s3_get_download_url(),
                    code=302,
                    local=False,
                )
        return super().content_common(
            xmlid=xmlid,
            model=model,
            id=id,
            field=field,
            filename=filename,
            download=download,
            access_token=access_token,
            nocache=nocache,
            **kwargs,
        )
