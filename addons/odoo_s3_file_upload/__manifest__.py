{
    "name": "Odoo S3 File Upload",
    "version": "19.0.1.0.0",
    "category": "Project",
    "summary": "S3-compatible direct uploads for project.task attachments",
    "depends": ["project", "mail"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/ir_attachment_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
