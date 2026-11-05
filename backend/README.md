# CloudGuard DR API

Standalone FastAPI backend for the existing CloudGuard DR frontend. It does not modify or serve the React application. All business APIs return `{ "success", "message", "data" }` envelopes.

## Requirements

- Python 3.12
- PostgreSQL 14+
- An AWS IAM identity with read-only access to the services being inventoried

The AWS account should use a dedicated read-only principal. See `docs/aws-read-only-policy.json` for a starting policy; scope it to the resources and regions your organization permits before use.

## Local setup

From this directory, create a virtual environment and install dependencies:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Replace the placeholder secrets in `.env`. Generate values with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Provision PostgreSQL and set `DATABASE_URL`. Then apply the schema and start the API:

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

Health: `GET http://127.0.0.1:8000/health`
Interactive API docs: `http://127.0.0.1:8000/docs`

## Authentication

1. `POST /api/auth/register` with `email`, `name`, and a password of at least 12 characters. Registration creates a private workspace.
2. `POST /api/auth/login` returns a short-lived bearer JWT.
3. Send `Authorization: Bearer <access_token>` to protected routes.
4. `GET /api/workspaces` lists the current user's workspaces; `POST /api/workspaces` creates one.

Workspace ownership is checked server-side for all AWS inventory and scan requests. Tokens expire after `JWT_ACCESS_TOKEN_MINUTES`; rotate the signing secret and invalidate active tokens during incident response.

## AWS workflow

1. `POST /api/aws/connect` with `workspace_id`, `account_name`, `access_key`, `secret_key`, and `region`. Credentials are validated with STS `GetCallerIdentity` and encrypted using Fernet before storage. The response returns the AWS account ID, ARN, and connection status only.
2. `POST /api/aws/scan` with `workspace_id` and optionally `account_id` or `region`.
3. Read the latest scan through `/api/aws/resources`, `/api/aws/readiness`, `/api/aws/recommendations`, `/api/aws/report`, and `/api/aws/history` using the `workspace_id` query parameter.

The scanner collects EC2, RDS, S3, IAM, CloudWatch, security groups, VPCs, Lambda, EBS volumes/snapshots, availability zones, and enabled regions. A scan with some service permission failures is persisted as `partial` with sanitized warnings; a scan that returns no resources fails with an appropriate HTTP error. Scanning is synchronous for this starter implementation, so place it behind a job queue for large accounts before high-volume production use.

## Security and operations

- Use HTTPS and a secrets manager for `JWT_SECRET_KEY` and `AWS_CREDENTIAL_ENCRYPTION_KEY`.
- Back up the Fernet key securely. Rotating it requires re-encrypting every stored AWS credential before replacing the active key.
- AWS secret keys are excluded from schemas and responses, encrypted at rest, and not written to application logs.
- Do not expose the API directly to the public internet without rate limiting, audit logging, network controls, and operational monitoring.
- CORS origins should contain only the deployed frontend origins.
- Use short-lived role credentials with external ID and `AssumeRole` instead of long-lived user keys for a production deployment. This endpoint accepts the keys requested by the initial integration contract.

## API overview

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET/POST /api/workspaces`
- `POST /api/aws/connect`, `POST /api/aws/scan`
- `GET /api/aws/resources?workspace_id=...&service=...&region=...&risk=...&search=...&page=1&page_size=25`
- `GET /api/aws/readiness?workspace_id=...`
- `GET /api/aws/recommendations?workspace_id=...&page=1&page_size=25`
- `GET /api/aws/report?workspace_id=...` (generates and stores a JSON report)
- `GET /api/aws/history?workspace_id=...&page=1&page_size=25`

