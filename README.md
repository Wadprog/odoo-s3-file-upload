# odoo-s3-file-upload

Odoo 19 module for S3-compatible direct uploads on `project.task` attachments.

See [docs/PRD-project-task-s3-attachments.md](docs/PRD-project-task-s3-attachments.md) for the product requirements.

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

Credentials are passed into the `web` service via `docker-compose.yaml` and are not stored in the Odoo database. Bucket and endpoint settings are added in a later slice.
