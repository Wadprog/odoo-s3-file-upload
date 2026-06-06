# odoo-s3-file-upload

Odoo 19 module for S3-compatible direct uploads on `project.task` attachments.

- **Documentation (GitHub Pages):** https://wadprog.github.io/odoo-s3-file-upload/
- **Product requirements:** [docs/PRD-project-task-s3-attachments.md](docs/PRD-project-task-s3-attachments.md)

## Local development

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

1. Create secrets and Odoo config:

   ```bash
   echo "your-db-password" > odoo_pg_pass
   cp config/odoo.conf.example config/odoo.conf
   ```

   Edit `config/odoo.conf` and set `db_password` to match `odoo_pg_pass`.

2. (Optional) Set S3-compatible storage credentials for the Odoo container:

   ```bash
   export S3_ACCESS_KEY_ID=your_access_key
   export S3_SECRET_ACCESS_KEY=your_secret_key
   # export S3_SESSION_TOKEN=your_session_token   # optional
   ```

3. Build and start:

   ```bash
   docker compose up --build -d
   ```

4. Open Odoo at http://localhost:8069, create a database, then install **Odoo S3 File Upload** from Apps.

### Verify boto3

```bash
docker compose exec web python3 -c "import boto3; print(boto3.__version__)"
```

### Module location

Addon path: `addons/odoo_s3_file_upload` (mounted at `/mnt/extra-addons` in the container).

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `S3_ACCESS_KEY_ID` | Yes (for storage) | Access key for AWS S3 or Cloudflare R2 |
| `S3_SECRET_ACCESS_KEY` | Yes (for storage) | Secret key for AWS S3 or Cloudflare R2 |
| `S3_SESSION_TOKEN` | No | Temporary session token (STS) |

Credentials are passed into the `web` service via `docker-compose.yaml` and are not stored in the Odoo database. Bucket and endpoint settings are configured in Odoo **Settings → S3 File Upload**.

## R2 / S3 CORS (required for browser uploads)

Uploads go **directly from the browser to storage**. If CORS is not configured on the bucket, uploads fail with `Failed to fetch` in the Odoo logs.

In **Cloudflare R2** → your bucket → **Settings** → **CORS policy**, add:

```json
[
  {
    "AllowedOrigins": [
      "http://localhost:8069",
      "https://your-odoo-domain.com"
    ],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

- Replace origins with your real Odoo URL(s).
- `ExposeHeaders: ETag` is required so multipart uploads can complete.
- After saving CORS, hard-refresh Odoo and retry the upload.

## Production deployment checklist

### Environment

| Item | Notes |
|------|--------|
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Set on the Odoo container (or host process). Never commit or store in the database. |
| Bucket settings | **Settings → S3 File Upload**: bucket name, region, endpoint (R2), key prefix, presigned TTL, path-style if required. |
| **Test Connection** | Run from Settings after deploy to confirm credentials and bucket access. |

### CORS

Configure the bucket for every Odoo origin (production, staging, localhost). Required methods: `GET`, `PUT`, `HEAD`. Expose `ETag` for multipart completion. See the JSON example in [R2 / S3 CORS](#r2--s3-cors-required-for-browser-uploads) above.

### Presigned URL TTL

Default is 3600 seconds (1 hour). Large files on slow links may need a higher TTL under **Presigned URL TTL**. The upload client re-requests part URLs on 403/400, but keeping TTL comfortably above expected upload duration reduces retries.

### Stale uploads

A daily cron aborts and deletes `pending` or `failed` task attachments older than **Stale Upload Cleanup** hours (default 24). Adjust under **Settings → S3 File Upload** if editors often leave drafts open overnight.

### Operations

1. **Upgrade module** after each deploy (`-u odoo_s3_file_upload`) so cron, views, and assets load.
2. **Hard-refresh browsers** after JS changes (or bump assets in production).
3. **Monitor logs** for `S3 upload failed for attachment` and storage `UserError` messages.
4. **R2 path-style**: enable in Settings if your provider requires it (Cloudflare R2 typically does).
5. **Backups**: attachment metadata lives in PostgreSQL; file bytes are in object storage — back up both.

### Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `Failed to fetch` on upload | Missing or wrong CORS on the bucket |
| Download returns placeholder image | Image route not upgraded; ensure module is latest |
| Upload stuck at 0% | Network block or presign failure; check Odoo server logs |
| `Storage connection failed` on Test Connection | Wrong bucket, endpoint, credentials, or path-style setting |
| Orphan `pending` rows | Wait for cron or lower stale-upload hours temporarily |
