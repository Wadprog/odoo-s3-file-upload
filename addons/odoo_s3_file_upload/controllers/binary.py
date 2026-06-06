from odoo import http
from odoo.http import request

from odoo.addons.web.controllers.binary import Binary


class S3BinaryController(Binary):
    """Redirect standard attachment downloads to presigned S3 URLs."""

    def _s3_redirect_task_attachment(self, model, attachment_id):
        """Return a redirect response for uploaded S3 task attachments, or None."""
        if model != "ir.attachment" or not attachment_id:
            return None
        attachment = request.env["ir.attachment"].browse(int(attachment_id)).exists()
        if not (
            attachment.s3_storage_status == "uploaded"
            and attachment.s3_key
            and attachment.res_model == "project.task"
        ):
            return None
        attachment.check_access("read")
        return request.redirect(
            attachment.s3_get_download_url(),
            code=302,
            local=False,
        )

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
        redirect = self._s3_redirect_task_attachment(model, id)
        if redirect:
            return redirect
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

    @http.route(
        [
            "/web/image",
            "/web/image/<string:xmlid>",
            "/web/image/<string:xmlid>/<string:filename>",
            "/web/image/<string:xmlid>/<int:width>x<int:height>",
            "/web/image/<string:xmlid>/<int:width>x<int:height>/<string:filename>",
            "/web/image/<string:model>/<int:id>/<string:field>",
            "/web/image/<string:model>/<int:id>/<string:field>/<string:filename>",
            "/web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>",
            "/web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>/<string:filename>",
            "/web/image/<int:id>",
            "/web/image/<int:id>/<string:filename>",
            "/web/image/<int:id>/<int:width>x<int:height>",
            "/web/image/<int:id>/<int:width>x<int:height>/<string:filename>",
            "/web/image/<int:id>-<string:unique>",
            "/web/image/<int:id>-<string:unique>/<string:filename>",
            "/web/image/<int:id>-<string:unique>/<int:width>x<int:height>",
            "/web/image/<int:id>-<string:unique>/<int:width>x<int:height>/<string:filename>",
        ],
        type="http",
        auth="public",
        readonly=True,
        save_session=False,
    )
    def content_image(
        self,
        xmlid=None,
        model="ir.attachment",
        id=None,
        field="raw",
        filename_field="name",
        filename=None,
        mimetype=None,
        unique=False,
        download=False,
        width=0,
        height=0,
        crop=False,
        access_token=None,
        nocache=False,
    ):
        redirect = self._s3_redirect_task_attachment(model, id)
        if redirect:
            return redirect
        return super().content_image(
            xmlid=xmlid,
            model=model,
            id=id,
            field=field,
            filename_field=filename_field,
            filename=filename,
            mimetype=mimetype,
            unique=unique,
            download=download,
            width=width,
            height=height,
            crop=crop,
            access_token=access_token,
            nocache=nocache,
        )
