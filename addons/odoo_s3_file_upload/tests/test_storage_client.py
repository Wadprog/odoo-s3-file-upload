import os
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.odoo_s3_file_upload.services.storage_client import S3StorageClient


class TestS3StorageClient(TransactionCase):
    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()
        self.icp.set_param("odoo_s3_file_upload.bucket_name", "test-bucket")
        self.icp.set_param("odoo_s3_file_upload.region", "us-east-1")
        self.icp.set_param("odoo_s3_file_upload.presigned_ttl_seconds", "3600")
        self.env_patch = patch.dict(
            os.environ,
            {
                "S3_ACCESS_KEY_ID": "test-access-key",
                "S3_SECRET_ACCESS_KEY": "test-secret-key",
            },
            clear=False,
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        super().tearDown()

    @patch("odoo.addons.odoo_s3_file_upload.services.storage_client.boto3.client")
    def test_aws_client_uses_default_endpoint(self, mock_boto_client):
        self.icp.set_param("odoo_s3_file_upload.endpoint_url", "")
        mock_boto_client.return_value.create_multipart_upload.return_value = {
            "UploadId": "upload-1"
        }

        client = S3StorageClient(self.env)
        upload_id = client.init_multipart("projects/1/tasks/2/file.pdf", "application/pdf")

        self.assertEqual(upload_id, "upload-1")
        _, kwargs = mock_boto_client.call_args
        self.assertIsNone(kwargs["endpoint_url"])
        self.assertEqual(kwargs["region_name"], "us-east-1")
        mock_boto_client.return_value.create_multipart_upload.assert_called_once_with(
            Bucket="test-bucket",
            Key="projects/1/tasks/2/file.pdf",
            ContentType="application/pdf",
        )

    @patch("odoo.addons.odoo_s3_file_upload.services.storage_client.boto3.client")
    def test_r2_client_uses_custom_endpoint_and_prefix(self, mock_boto_client):
        endpoint = "https://account123.r2.cloudflarestorage.com"
        self.icp.set_param("odoo_s3_file_upload.endpoint_url", endpoint)
        self.icp.set_param("odoo_s3_file_upload.key_prefix", "dev")
        self.icp.set_param("odoo_s3_file_upload.use_path_style", "True")
        mock_boto_client.return_value.generate_presigned_url.return_value = (
            "https://signed.example/get"
        )

        client = S3StorageClient(self.env)
        url = client.presign_get("projects/1/tasks/2/file.pdf")

        self.assertEqual(url, "https://signed.example/get")
        _, kwargs = mock_boto_client.call_args
        self.assertEqual(kwargs["endpoint_url"], endpoint)
        mock_boto_client.return_value.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "test-bucket",
                "Key": "dev/projects/1/tasks/2/file.pdf",
            },
            ExpiresIn=3600,
        )

    @patch("odoo.addons.odoo_s3_file_upload.services.storage_client.boto3.client")
    def test_head_object_returns_none_for_missing_key(self, mock_boto_client):
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_boto_client.return_value.head_object.side_effect = ClientError(
            error_response, "HeadObject"
        )

        client = S3StorageClient(self.env)
        self.assertIsNone(client.head_object("missing/file.pdf"))

    def test_missing_credentials_raise_user_error(self):
        with patch.dict(os.environ, {}, clear=True):
            client = S3StorageClient(self.env)
            with self.assertRaises(UserError):
                client.presign_get("file.pdf")
