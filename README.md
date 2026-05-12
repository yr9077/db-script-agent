# Database Script Agent

A database script copilot for small internal teams. It reads real schema metadata from MySQL and PostgreSQL, generates draft SQL scripts from natural language, and returns explanations, risks, and impacted objects.

Current implementation status:
- schema-aware generation based on saved snapshots
- mock and llm generation backends
- structured validation with syntax, schema, and performance categories
- generation history with list filtering and sorting
- human review feedback with final script and diff tracking

## Scope

Version 1 only supports:
- MySQL and PostgreSQL
- Web API usage
- Draft generation only, no execution
- Schema snapshot based generation
- Human review and final script tracking

## Project Layout

- docs/: project docs and delivery plan
- app/: application code
- tests/: API, service, and db tool tests

Useful docs:
- docs/05-api-contracts.md: endpoint and field contracts
- docs/07-frontend-integration.md: recommended UI data usage and rendering rules
- docs/08-testing-and-acceptance.md: regression checklist and acceptance scenarios
- docs/09-production-and-migrations.md: technical debt, migration strategy, and production notes

Key modules:
- app/agent/: prompt builder, parser, llm client, orchestrator
- app/tools/: sql lint and risk checks
- app/services/: connection, schema, generation workflows
- app/storage/: ORM models and database session

## Development Plan

1. Write docs and contracts
2. Build storage models and schemas
3. Build services and db tools
4. Add mock generation flow
5. Replace mock backend with real LLM backend

## Setup

1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies

```powershell
pip install -e .[dev]
```

3. Copy the environment file

```powershell
Copy-Item .env.example .env
```

4. Configure generation backend in `.env`

For local development, keep the default mock backend:

```env
APP_GENERATION_BACKEND=mock
APP_GENERATION_TIMEOUT_SECONDS=300
```

Schema bootstrap behavior:

```env
APP_DB_AUTO_CREATE=true
```

For persistent or migration-managed environments, disable automatic schema creation:

```env
APP_DB_AUTO_CREATE=false
```

Optional internal auth for business API requests:

```env
APP_AUTH_ENABLED=true
APP_AUTH_MODE=token
APP_INTERNAL_API_TOKEN=replace-with-a-team-secret
APP_INTERNAL_TOKEN_HEADER=X-Internal-Token
APP_INTERNAL_REVIEWER_HEADER=X-Internal-Reviewer
```

Recommended HMAC mode for service identity and request signing:

```env
APP_AUTH_ENABLED=true
APP_AUTH_MODE=hmac
APP_INTERNAL_HMAC_SECRET=replace-with-a-long-random-secret
APP_INTERNAL_PRINCIPAL_HEADER=X-Internal-Principal
APP_INTERNAL_TIMESTAMP_HEADER=X-Internal-Timestamp
APP_INTERNAL_SIGNATURE_HEADER=X-Internal-Signature
APP_INTERNAL_REVIEWER_HEADER=X-Internal-Reviewer
APP_INTERNAL_HMAC_MAX_AGE_SECONDS=300
```

Optional client default for CLI tools:

```env
APP_API_BASE_URL=http://127.0.0.1:8000
```

To use a real LLM backend, switch to:

```env
APP_GENERATION_BACKEND=llm
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4.1-mini
```

AI management endpoints:
- `GET /api/ai/backend/status`: returns current backend mode and whether LLM env config is complete
- `POST /api/ai/backend/test`: tests the configured or submitted OpenAI-compatible endpoint by calling `/models`
- `GET /ui/ai`: browser UI for checking config state and testing connectivity

5. Generate a Fernet key and set it in `.env`

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

6. Start the API server

```powershell
uvicorn app.main:app --reload
```

7. Run tests

```powershell
pytest
```

8. Run Alembic migrations on a fresh metadata database

```powershell
python -m alembic upgrade head
```

If the target database already contains the current baseline schema and you only need to mark it as managed:

```powershell
python -m alembic stamp 20260423_000006
```

If your metadata database uses native enums, such as PostgreSQL or MySQL, make sure the latest migrations are applied before using cancellation flows. Revision `20260423_000006` extends `generationstatusenum` to include `canceled`.

When internal auth is enabled, all `/api/*` requests must use the configured auth mode. `GET /health` remains open for liveness checks.

Auth mode summary:
- `token`: send the configured token header on every `/api/*` request
- `hmac`: send principal, timestamp, and signature headers on every `/api/*` request
- review requests still support the reviewer header, but in HMAC mode the principal is used as reviewer by default

HMAC canonical payload:

```text
{METHOD}\n{PATH}\n{QUERY_STRING}\n{PRINCIPAL}\n{TIMESTAMP}\n{SHA256_HEX_OF_BODY}
```

Helper tool for HMAC headers:

```powershell
dbsa-sign-request --secret replace-with-a-long-random-secret --method POST --path /api/generations --principal svc-db-agent --timestamp 1713772800 --body '{"connection_id":"...","snapshot_id":"...","request_text":"show latest orders","script_mode":"query"}'
```

The command prints a JSON object containing the correct auth headers for the request.

Helper tool for signed API calls:

```powershell
dbsa-call-api --base-url http://127.0.0.1:8000 --auth-mode hmac --secret replace-with-a-long-random-secret --principal svc-db-agent --method GET --path /api/history --query review_status=edited --query has_final_script=true
```

The command signs the request, sends it to the API, prints the HTTP status, and then prints the JSON response body when possible.

If `.env` already defines `APP_API_BASE_URL`, `APP_AUTH_MODE`, and the matching auth settings, you can use a shorter form:

```powershell
dbsa-call-api --method GET --path /api/history --query review_status=edited --query has_final_script=true

dbsa-call-api --method GET --path /api/history --query latest_status=failed
```

Built-in request presets:

```powershell
dbsa-call-api --preset create-connection --connection-name orders-prod-ro --dialect mysql --host 127.0.0.1 --port 3306 --database-name orders --username readonly_user --connection-auth-mode password --secret-file .\db-secret.txt
dbsa-call-api --preset verify-connection --connection-id <connection-id>
dbsa-call-api --preset history-list --review-status edited --has-final-script --sort-by last_reviewed_at --sort-order desc
dbsa-call-api --preset history-list --latest-status failed
dbsa-call-api --preset refresh-schema --connection-id <connection-id>
dbsa-call-api --preset create-generation --connection-id <connection-id> --snapshot-id <snapshot-id> --request-text 'show latest orders' --script-mode query
dbsa-call-api --preset generation-status --request-id <generation-id>
dbsa-call-api --preset execute-generation --request-id <generation-id>
dbsa-call-api --preset retry-generation --request-id <generation-id>
dbsa-call-api --preset cancel-generation --request-id <generation-id>
dbsa-call-api --preset generation-detail --request-id <generation-id>
dbsa-call-api --preset submit-review --request-id <generation-id> --review-status edited --review-note 'Adjusted the sample size' --final-script-text 'SELECT * FROM orders LIMIT 20;'
```

Preset summary:
- `create-connection`: wraps `POST /api/connections`; use `--connection-secret` or `--secret-file` for the database credential, while HMAC auth still uses `--secret`
- `create-connection` fails fast when `--secret-file` is missing or only contains whitespace
- `submit-review` fails fast when `--final-script-text-file` is missing or only contains whitespace
- `verify-connection`: wraps `POST /api/connections/{id}/verify`
- `history-list`: wraps `GET /api/history` and supports common filter/sort flags
- `history-list` latest-status values: `queued`, `running`, `completed`, `failed`, `canceled`, `clarification_needed`
- `history-list` review-status values: `accepted`, `rejected`, `edited`
- `history-list` lint-status values: `pass`, `warn`, `fail`
- `history-list` sort-by values: `created_at`, `last_reviewed_at`, `risk_count`
- `history-list` sort-order values: `asc`, `desc`
- `history-list` page must be `>= 1`, and `page-size` must be between `1` and `100`
- `refresh-schema`: wraps `POST /api/connections/{id}/schema/refresh`
- `create-generation`: wraps `POST /api/generations` and creates a queued generation task; `--request-text` is trimmed, must not be blank, and is limited to `4000` characters
- `generation-status`: wraps `GET /api/generations/{id}/status`
- `execute-generation`: wraps `POST /api/generations/{id}/execute`
- `retry-generation`: wraps `POST /api/generations/{id}/retry` for failed tasks
- `cancel-generation`: wraps `POST /api/generations/{id}/cancel` for queued or running tasks
- `generation-detail`: wraps `GET /api/generations/{id}` after execution completes
- `submit-review`: wraps `POST /api/history/{id}/review`

Operator flow example:

```powershell
dbsa-call-api --preset create-connection --connection-name orders-prod-ro --dialect mysql --host 127.0.0.1 --port 3306 --database-name orders --username readonly_user --connection-auth-mode password --secret-file .\db-secret.txt
dbsa-call-api --preset verify-connection --connection-id <connection-id>
dbsa-call-api --preset refresh-schema --connection-id <connection-id>
dbsa-call-api --preset create-generation --connection-id <connection-id> --snapshot-id <snapshot-id> --request-text 'show latest orders' --script-mode query
dbsa-call-api --preset generation-status --request-id <generation-id>
dbsa-call-api --preset execute-generation --request-id <generation-id>
dbsa-call-api --preset retry-generation --request-id <generation-id>
dbsa-call-api --preset cancel-generation --request-id <generation-id>
dbsa-call-api --preset generation-detail --request-id <generation-id>
dbsa-call-api --preset submit-review --request-id <generation-id> --review-status edited --final-script-text 'SELECT * FROM orders LIMIT 20;'
```

## Available Endpoints

- `GET /health`
- `POST /api/connections`
- `POST /api/connections/{id}/verify`
- `POST /api/connections/{id}/schema/refresh`
- `POST /api/generations`
- `GET /api/generations/{id}/status`
- `POST /api/generations/{id}/execute`
- `POST /api/generations/{id}/retry`
- `POST /api/generations/{id}/cancel`
- `GET /api/generations/{id}`
- `GET /api/history`
- `GET /api/history/{id}`
- `POST /api/history/{id}/review`

## Recommended Workflow

1. Create a connection profile.
2. Verify that the connection can read metadata.
3. Refresh a schema snapshot.
4. Create a generation request using that snapshot.
5. Trigger generation execution.
6. Poll generation status until it reaches a terminal state.
7. Read generation detail and use `effective_script_text` as the default script shown to users.
8. Record review feedback if the script is accepted, rejected, or manually edited.
9. Use the history list for filtering, sorting, and review tracking.

## Key Response Concepts

Generation detail and history detail both expose:
- `generated_script`: the original agent output
- `effective_script_text`: the script the UI should currently treat as authoritative

Review responses keep `edited_script_text` only as a compatibility alias for `final_script_text`.

Validation is structured as:
- `lint_status`
- `lint_messages`
- `syntax_issues`
- `schema_issues`
- `performance_warnings`

Generation status responses also expose:
- `attempt_count`: how many execution attempts have been started for this request
- `started_at`: the latest execution start time
- `finished_at`: the latest execution finish time when the attempt reached a terminal state
- `error_message`: last execution failure reason when status is `failed`
- `can_retry`: whether `POST /api/generations/{id}/retry` is currently allowed
- `can_cancel`: whether `POST /api/generations/{id}/cancel` is currently allowed

History list includes lightweight summary fields so a list page does not need per-row detail fetches:
- `latest_status`
- `attempt_count`
- `last_error_message`
- `lint_status`
- `risk_count`
- `review_status`
- `last_reviewed_at`
- `has_final_script`

## Example Workflow

Create a generation request in token mode:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/generations -ContentType 'application/json' -Headers @{'X-Internal-Token'='replace-with-a-team-secret'} -Body '{
	"connection_id": "<connection-id>",
	"snapshot_id": "<snapshot-id>",
	"request_text": "show latest orders",
	"script_mode": "query"
}'
```

Execute the queued generation and check status in token mode:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/generations/<generation-id>/execute -Headers @{'X-Internal-Token'='replace-with-a-team-secret'}
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/generations/<generation-id>/status -Headers @{'X-Internal-Token'='replace-with-a-team-secret'}
```

Retry a failed generation in token mode:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/generations/<generation-id>/retry -Headers @{'X-Internal-Token'='replace-with-a-team-secret'}
```

Cancel a queued or running generation in token mode:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/generations/<generation-id>/cancel -Headers @{'X-Internal-Token'='replace-with-a-team-secret'}
```

Record an edited review with a final script in token mode:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/history/<generation-id>/review -ContentType 'application/json' -Headers @{'X-Internal-Token'='replace-with-a-team-secret';'X-Internal-Reviewer'='alice'} -Body '{
	"review_status": "edited",
	"review_note": "Adjusted the sample size",
	"final_script_text": "SELECT * FROM orders LIMIT 20;"
}'
```

Filter history by review state and final-script availability:

```powershell
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/api/history?review_status=edited&has_final_script=true&sort_by=last_reviewed_at&sort_order=desc' -Headers @{'X-Internal-Token'='replace-with-a-team-secret'}
```

In HMAC mode, compute the signature from the canonical payload above and send these headers on each `/api/*` request:
- `X-Internal-Principal`
- `X-Internal-Timestamp`
- `X-Internal-Signature`
- optional `X-Internal-Reviewer` override for review actions

For local tooling and service integration tests, you can generate these headers with `dbsa-sign-request` instead of implementing the signing logic yourself.

If you want a single command that signs and sends the request, use `dbsa-call-api`.

## Example Responses

Generation detail example:

```json
{
	"generation_id": "9b3f7d2d-7d4d-4d5d-a7d0-2cccb9155d3d",
	"status": "completed",
	"request_summary": "show latest orders",
	"db_dialect": "mysql",
	"assumptions": [
		"orders has created_at",
		"mock generation path is active"
	],
	"plan_steps": [
		"Load schema",
		"Draft script",
		"Run validation"
	],
	"generated_script": "-- mock script\nSELECT * FROM orders LIMIT 10;",
	"effective_script_text": "SELECT * FROM orders LIMIT 20;",
	"explanation": "Mock result used to validate the persistence chain.",
	"risks": [
		{
			"level": "low",
			"code": "mock_result",
			"message": "Mock result only"
		}
	],
	"impacted_objects": [
		{
			"type": "table",
			"name": "orders"
		}
	],
	"unresolved_questions": [
		"Should a stricter filter be applied?"
	],
	"confidence_score": 0.6,
	"references": [
		{
			"type": "schema_object",
			"name": "orders"
		}
	],
	"validation": {
		"lint_status": "warn",
		"lint_messages": [
			"Mock validation path"
		],
		"syntax_issues": [],
		"schema_issues": [],
		"performance_warnings": [
			"Mock validation path"
		]
	}
}
```

History list example:

```json
{
	"items": [
		{
			"request_id": "9b3f7d2d-7d4d-4d5d-a7d0-2cccb9155d3d",
			"request_summary": "show latest orders",
			"script_mode": "query",
			"dialect": "mysql",
			"lint_status": "warn",
			"risk_count": 1,
			"review_status": "edited",
			"last_reviewed_at": "2026-04-22T12:34:56.000000",
			"has_final_script": true,
			"created_at": "2026-04-22T12:30:00.000000"
		}
	],
	"pagination": {
		"page": 1,
		"page_size": 20,
		"total": 1
	}
}
```

Review feedback response example:

```json
{
	"request_id": "9b3f7d2d-7d4d-4d5d-a7d0-2cccb9155d3d",
	"review_status": "edited",
	"reviewer": "alice",
	"review_note": "Adjusted the sample size",
	"edited_script_text": "SELECT * FROM orders LIMIT 20;",
	"final_script_text": "SELECT * FROM orders LIMIT 20;",
	"edited_script_diff": "--- generated.sql\n+++ final.sql\n@@ -1,2 +1 @@\n--- mock script\n-SELECT * FROM orders LIMIT 10;\n+SELECT * FROM orders LIMIT 20;",
	"created_at": "2026-04-22T12:34:56.000000"
}
```

History detail example:

```json
{
	"request_id": "9b3f7d2d-7d4d-4d5d-a7d0-2cccb9155d3d",
	"request_text": "show latest orders",
	"plan_steps": [
		"Load schema",
		"Draft script",
		"Run validation"
	],
	"generated_script": "-- mock script\nSELECT * FROM orders LIMIT 10;",
	"effective_script_text": "SELECT * FROM orders LIMIT 20;",
	"risks": [
		{
			"level": "low",
			"code": "mock_result",
			"message": "Mock result only"
		}
	],
	"validation": {
		"lint_status": "warn",
		"lint_messages": [
			"Mock validation path"
		],
		"syntax_issues": [],
		"schema_issues": [],
		"performance_warnings": [
			"Mock validation path"
		]
	},
	"review_feedback": [
		{
			"review_status": "edited",
			"reviewer": "alice",
			"review_note": "Adjusted the sample size",
			"edited_script_text": "SELECT * FROM orders LIMIT 20;",
			"final_script_text": "SELECT * FROM orders LIMIT 20;",
			"edited_script_diff": "--- generated.sql\n+++ final.sql\n@@ -1,2 +1 @@\n--- mock script\n-SELECT * FROM orders LIMIT 10;\n+SELECT * FROM orders LIMIT 20;",
			"created_at": "2026-04-22T12:34:56.000000"
		}
	]
}
```

## Generation Backends

- `mock`: returns deterministic draft output for local development and test validation
- `llm`: calls an OpenAI-compatible `/chat/completions` endpoint and then runs local lint and risk analysis

If `llm` is enabled but the model config is missing or invalid, generation will fail instead of silently falling back to mock output.
