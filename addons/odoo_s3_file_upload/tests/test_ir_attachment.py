import base64
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

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
        self.head_results = {}

    def init_multipart(self, key, content_type=None):
        return "upload-abc"

    def abort_multipart(self, key, upload_id):
        self.aborted.append((key, upload_id))

    def head_object(self, key):
        return self.head_results.get(key)

    def presign_get(self, key):
        return f"https://signed.example/{key}"

    def complete_multipart(self, key, upload_id, parts):
        return {"ETag": '"etag-1"'}


@patch("odoo.addons.odoo_s3_file_upload.models.ir_attachment.get_storage_client")
class TestIrAttachmentS3(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create(
            {
                "name": "Test Project",
                "privacy_visibility": "followers",
            }
        )
        cls.task = cls.env["project.task"].create(
            {"name": "Test Task", "project_id": cls.project.id}
        )
        cls.portal_user = cls.env["res.users"].create(
            {
                "name": "Portal User",
                "login": "portal_s3_test_user",
                "email": "portal_s3_test@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

    def _mock_client(self, mock_get_client):
        client = MockStorageClient()
        mock_get_client.return_value = client
        return client

    def test_guard_rejects_local_binary_on_project_task(self, mock_get_client):
        self._mock_client(mock_get_client)
        with self.assertRaises(UserError):
            self.env["ir.attachment"].create(
                {
                    "name": "local.pdf",
                    "res_model": "project.task",
                    "res_id": self.task.id,
                    "datas": base64.b64encode(b"local-data"),
                }
            )

    def test_blocklist_rejects_exe_on_pending_create(self, mock_get_client):
        self._mock_client(mock_get_client)
        with self.assertRaises(UserError):
            self.env["ir.attachment"].s3_create_pending(
                self.task.id, "virus.exe", "application/octet-stream", 10
            )

    def test_create_pending_sets_empty_binary_and_key(self, mock_get_client):
        self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        self.assertEqual(attachment.s3_storage_status, S3_STATUS_PENDING)
        self.assertTrue(attachment.s3_key.startswith("projects/"))
        self.assertFalse(attachment.datas)

    def test_lifecycle_pending_to_uploaded(self, mock_get_client):
        self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        attachment.s3_mark_uploaded(etag='"etag-1"')
        self.assertEqual(attachment.s3_storage_status, S3_STATUS_UPLOADED)
        self.assertEqual(attachment.s3_etag, '"etag-1"')

    def test_lifecycle_pending_to_failed(self, mock_get_client):
        client = self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        attachment.with_context(s3_upload_allowed=True).write(
            {"s3_upload_id": "upload-abc"}
        )
        attachment.s3_mark_failed()
        self.assertEqual(attachment.s3_storage_status, S3_STATUS_FAILED)
        self.assertEqual(client.aborted, [(attachment.s3_key, "upload-abc")])

    def test_lifecycle_cancel_deletes_pending_attachment(self, mock_get_client):
        client = self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        attachment_id = attachment.id
        s3_key = attachment.s3_key
        attachment.with_context(s3_upload_allowed=True).write(
            {"s3_upload_id": "upload-abc"}
        )
        attachment.s3_cancel()
        self.assertFalse(self.env["ir.attachment"].browse(attachment_id).exists())
        self.assertEqual(client.aborted, [(s3_key, "upload-abc")])

    def test_retry_reuses_key_when_object_missing(self, mock_get_client):
        client = self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        original_key = attachment.s3_key
        client.head_results[original_key] = None
        resolved = attachment.s3_resolve_retry_key()
        self.assertEqual(resolved, original_key)
        self.assertEqual(attachment.s3_key, original_key)

    def test_retry_rotates_key_when_object_exists(self, mock_get_client):
        client = self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        original_key = attachment.s3_key
        client.head_results[original_key] = {"ContentLength": 10}
        resolved = attachment.s3_resolve_retry_key()
        self.assertNotEqual(resolved, original_key)
        self.assertEqual(attachment.s3_key, resolved)
        self.assertEqual(attachment.s3_storage_status, S3_STATUS_PENDING)

    def test_download_requires_uploaded_status(self, mock_get_client):
        self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        with self.assertRaises(UserError):
            attachment.s3_get_download_url()

    def test_download_returns_presigned_url_for_authorized_user(self, mock_get_client):
        self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        attachment.s3_mark_uploaded(etag='"etag-1"')
        url = attachment.s3_get_download_url()
        self.assertTrue(url.startswith("https://signed.example/"))

    def test_download_denied_for_user_without_task_access(self, mock_get_client):
        self._mock_client(mock_get_client)
        attachment = self.env["ir.attachment"].s3_create_pending(
            self.task.id, "draft.pdf", "application/pdf", 1200
        )
        attachment.s3_mark_uploaded(etag='"etag-1"')
        with self.assertRaises(AccessError):
            attachment.with_user(self.portal_user).s3_get_download_url()
