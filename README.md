# employee-workflow-api

FastAPI microservice for employee workflows and real-time notifications.

Features:
- Create/list leave requests.
- Update leave status.
- Persist notifications in PostgreSQL.
- Push real-time events with WebSockets.

## Local run

Use the same local PostgreSQL container as the directory service:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8002
```

Open:
- http://localhost:8002/docs
- http://localhost:8002/api/workflows/health

WebSocket:
- ws://localhost:8002/ws/notifications/1

## Important production note

The in-memory WebSocket connection manager is intentionally appropriate for the lab where the service has desired count 1. If you scale to multiple workflow tasks, use a shared event layer such as Redis/ElastiCache, SNS/SQS, or another broker.

GitHub repository variable:
- `AWS_ROLE_ARN` from Terraform output `workflow_deploy_role_arn`.
