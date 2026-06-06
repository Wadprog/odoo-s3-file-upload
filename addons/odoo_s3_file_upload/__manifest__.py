{
    "name": "Odoo S3 File Upload",
    "version": "19.0.1.0.0",
    "category": "Project",
    "summary": "S3-compatible direct uploads for project.task attachments",
    "depends": ["project", "mail", "web"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/ir_attachment_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            (
                "after",
                "mail/static/src/core/common/attachment_upload_service.js",
                "odoo_s3_file_upload/static/src/js/s3_multipart_upload.js",
            ),
            (
                "after",
                "mail/static/src/core/common/attachment_upload_service.js",
                "odoo_s3_file_upload/static/src/js/attachment_upload_service_patch.js",
            ),
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
