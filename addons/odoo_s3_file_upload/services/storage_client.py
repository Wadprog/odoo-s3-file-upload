import logging
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_BLOCKLIST = ".exe,.bat,.cmd,.msi,.scr,.ps1,.vbs"


class S3StorageClient:
    """S3-compatible storage client (AWS S3 or Cloudflare R2)."""

    def __init__(self, env):
        self.env = env
        icp = env["ir.config_parameter"].sudo()
        self.bucket = icp.get_param("odoo_s3_file_upload.bucket_name", "")
        self.region = icp.get_param("odoo_s3_file_upload.region", "us-east-1")
        endpoint = icp.get_param("odoo_s3_file_upload.endpoint_url", "")
        self.endpoint_url = endpoint or None
        self.key_prefix = icp.get_param("odoo_s3_file_upload.key_prefix", "").strip("/")
        self.presigned_ttl = int(icp.get_param("odoo_s3_file_upload.presigned_ttl_seconds", "3600"))
        self.use_path_style = icp.get_param("odoo_s3_file_upload.use_path_style", "False") == "True"
        self.blocklist_extensions = icp.get_param(
            "odoo_s3_file_upload.blocklist_extensions", DEFAULT_BLOCKLIST
        )

    def _validate_config(self):
        if not self.bucket:
            raise UserError(_("S3 bucket name is not configured. Set it in Settings."))
        if not os.environ.get("S3_ACCESS_KEY_ID") or not os.environ.get("S3_SECRET_ACCESS_KEY"):
            raise UserError(
                _(
                    "S3 credentials are missing. Set S3_ACCESS_KEY_ID and "
                    "S3_SECRET_ACCESS_KEY in the container environment."
                )
            )

    def _session_kwargs(self):
        self._validate_config()
        kwargs = {
            "aws_access_key_id": os.environ["S3_ACCESS_KEY_ID"],
            "aws_secret_access_key": os.environ["S3_SECRET_ACCESS_KEY"],
        }
        session_token = os.environ.get("S3_SESSION_TOKEN")
        if session_token:
            kwargs["aws_session_token"] = session_token
        return kwargs

    def _client(self):
        config = Config(s3={"addressing_style": "path" if self.use_path_style else "auto"})
        return boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
            config=config,
            **self._session_kwargs(),
        )

    def build_key(self, key):
        if self.key_prefix:
            return f"{self.key_prefix}/{key}"
        return key

    def test_connection(self):
        try:
            self._client().head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            _logger.error("S3 connection test failed for bucket %s: %s", self.bucket, exc)
            raise UserError(_("Storage connection failed: %s", exc)) from exc

    def init_multipart(self, key, content_type=None):
        params = {"Bucket": self.bucket, "Key": self.build_key(key)}
        if content_type:
            params["ContentType"] = content_type
        try:
            response = self._client().create_multipart_upload(**params)
            return response["UploadId"]
        except ClientError as exc:
            _logger.error("S3 init_multipart failed for key %s: %s", key, exc)
            raise UserError(_("Failed to start multipart upload: %s", exc)) from exc

    def presign_part(self, key, upload_id, part_number):
        try:
            return self._client().generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self.bucket,
                    "Key": self.build_key(key),
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=self.presigned_ttl,
            )
        except ClientError as exc:
            _logger.error("S3 presign_part failed for key %s part %s: %s", key, part_number, exc)
            raise UserError(_("Failed to presign upload part: %s", exc)) from exc

    def complete_multipart(self, key, upload_id, parts):
        try:
            return self._client().complete_multipart_upload(
                Bucket=self.bucket,
                Key=self.build_key(key),
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except ClientError as exc:
            _logger.error("S3 complete_multipart failed for key %s: %s", key, exc)
            raise UserError(_("Failed to complete multipart upload: %s", exc)) from exc

    def abort_multipart(self, key, upload_id):
        try:
            self._client().abort_multipart_upload(
                Bucket=self.bucket,
                Key=self.build_key(key),
                UploadId=upload_id,
            )
        except ClientError as exc:
            _logger.error("S3 abort_multipart failed for key %s: %s", key, exc)
            raise UserError(_("Failed to abort multipart upload: %s", exc)) from exc

    def head_object(self, key):
        try:
            return self._client().head_object(Bucket=self.bucket, Key=self.build_key(key))
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            _logger.error("S3 head_object failed for key %s: %s", key, exc)
            raise UserError(_("Failed to check object: %s", exc)) from exc

    def presign_get(self, key):
        try:
            return self._client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": self.build_key(key)},
                ExpiresIn=self.presigned_ttl,
            )
        except ClientError as exc:
            _logger.error("S3 presign_get failed for key %s: %s", key, exc)
            raise UserError(_("Failed to presign download URL: %s", exc)) from exc


def get_storage_client(env):
    return S3StorageClient(env)
