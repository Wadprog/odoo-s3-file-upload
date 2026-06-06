import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.odoo_s3_file_upload.controllers.s3_upload import S3UploadController
from odoo.addons.odoo_s3_file_upload.models.ir_attachment import (
    S3_STATUS_FAILED,
    S3_STATUS_PENDING,
    S3_STATUS_UPLOADED,
)


class MockStorageClient:
    bucket = "test-bucket"
    blocklist_extensions = ".exe,.bat"
    endpoint_url = None

    def __init__(self):
        self.aborted = []

    def init_multipart(self, key, content_type=None):
        return "upload-abc"

    def presign_part(self, key, upload_id, part_number):
        return f"https://signed.example/part/{part_number}"

    def complete_multipart(self, key, upload_id, parts):
        return {"ETag": '"etag-1"'}

    def abort_multipart(self, key, upload_id):
        self.aborted.append((key, upload_id))

    def presign_get(self, key):
        return f"https://signed.example/{key}"


@patch("odoo.addons.odoo_s3_file_upload.models.ir_attachment.get_storage_client")
class TestS3UploadController(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(
            "odoo_s3_file_upload.bucket_name", "test-bucket"
        )
        cls.env_patch = patch.dict(
            os.environ,
            {
                "S3_ACCESS_KEY_ID": "test-access-key",
                "S3_SECRET_ACCESS_KEY": "test-secret-key",
            },
            clear=False,
        )
        cls.env_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.env_patch.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.controller = S3UploadController()
        self.project = self.env["project.project"].create({"name": "RPC Project"})
        self.task = self.env["project.task"].create(
            {"name": "RPC Task", "project_id": self.project.id}
        )

    def _mock_storage(self, mock_get_client):
        client = MockStorageClient()
        mock_get_client.return_value = client
        return client

    @contextmanager
    def _request_env(self):
        mock_request = MagicMock()
        mock_request.env = self.env
        with patch(
            "odoo.addons.odoo_s3_file_upload.controllers.s3_upload.request",
            mock_request,
        ):
            yield

    def test_create_pending_returns_attachment_metadata(self, mock_get_client):
        self._mock_storage(mock_get_client)
        with self._request_env():
            result = self.controller.create_pending(
                self.task.id, "brief.pdf", "application/pdf", 4096
            )
        self.assertIn("attachment_id", result)
        self.assertIn("s3_key", result)
        self.assertIn("part_size", result)
        attachment = self.env["ir.attachment"].browse(result["attachment_id"])
        self.assertEqual(attachment.s3_storage_status, S3_STATUS_PENDING)

    def test_init_presign_complete_finalize_flow(self, mock_get_client):
        self._mock_storage(mock_get_client)
        with self._request_env():
            pending = self.controller.create_pending(
                self.task.id, "brief.pdf", "application/pdf", 10
            )
            attachment_id = pending["attachment_id"]

            init_result = self.controller.init_upload(attachment_id)
            self.assertEqual(init_result["upload_id"], "upload-abc")

            presign = self.controller.presign_part(attachment_id, "upload-abc", 1)
            self.assertTrue(presign["presigned_url"].startswith("https://"))

            self.controller.complete_upload(
                attachment_id,
                "upload-abc",
                [{"part_number": 1, "etag": '"etag-1"'}],
            )
            finalize = self.controller.finalize_upload(attachment_id)
        self.assertEqual(finalize["status"], S3_STATUS_UPLOADED)

    def test_fail_marks_attachment_failed(self, mock_get_client):
        self._mock_storage(mock_get_client)
        with self._request_env():
            pending = self.controller.create_pending(
                self.task.id, "brief.pdf", "application/pdf", 10
            )
            attachment_id = pending["attachment_id"]
            result = self.controller.fail_upload(attachment_id, reason="network")
        self.assertEqual(result["status"], S3_STATUS_FAILED)

    def test_get_download_url_requires_uploaded_attachment(self, mock_get_client):
        self._mock_storage(mock_get_client)
        with self._request_env():
            pending = self.controller.create_pending(
                self.task.id, "brief.pdf", "application/pdf", 10
            )
            attachment_id = pending["attachment_id"]
            with self.assertRaises(UserError):
                self.controller.get_download_url(attachment_id)

            attachment = self.env["ir.attachment"].browse(attachment_id)
            attachment.s3_mark_uploaded(etag='"etag-1"')
            result = self.controller.get_download_url(attachment_id)
        self.assertTrue(result["download_url"].startswith("https://"))
