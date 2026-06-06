{
    "name": "Odoo S3 File Upload",
    "version": "19.0.1.0.0",
    "category": "Project",
    "summary": "S3-compatible direct uploads for project.task attachments",
    "description": """
        <p>
            Direct browser uploads and downloads for <strong>project.task</strong> attachments
            on S3-compatible storage (AWS S3 or Cloudflare R2). Odoo handles permissions and
            metadata; file bytes travel between the browser and object storage only.
        </p>
        <p>
            <a href="https://wadprog.github.io/odoo-s3-file-upload/" target="_blank" rel="noopener">
                Documentation and more info
            </a>
        </p>
    """,
    "author": "C3 Edition Publishing",
    "website": "https://wadprog.github.io/odoo-s3-file-upload/",
    "depends": ["project", "mail", "web"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/ir_attachment_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            (
                "after",
                "web/static/src/views/fields/file_handler.js",
                "odoo_s3_file_upload/static/src/js/file_uploader_patch.js",
            ),
            (
                "after",
                "mail/static/src/chatter/web/chatter_patch.js",
                "odoo_s3_file_upload/static/src/js/chatter_patch.js",
            ),
            "odoo_s3_file_upload/static/src/xml/chatter_patch.xml",
            (
                "after",
                "mail/static/src/core/common/attachment_uploader_hook.js",
                "odoo_s3_file_upload/static/src/js/attachment_uploader_hook_patch.js",
            ),
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
            "odoo_s3_file_upload/static/src/js/s3_download.js",
            (
                "after",
                "mail/static/src/core/common/attachment_list.js",
                "odoo_s3_file_upload/static/src/js/attachment_list_patch.js",
            ),
            (
                "after",
                "web/static/src/core/file_viewer/file_viewer.js",
                "odoo_s3_file_upload/static/src/js/file_viewer_patch.js",
            ),
            "odoo_s3_file_upload/static/src/xml/file_viewer_patch.xml",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
