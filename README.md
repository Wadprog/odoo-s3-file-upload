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
