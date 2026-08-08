from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_session, initialize_database
from .models import LeaveRequest, Notification
from .schemas import LeaveCreate, LeaveOut, LeaveStatusUpdate, NotificationOut
from .websocket_manager import manager
from .auth import (
    CurrentUser,
    decode_access_token,
    get_current_user,
    require_roles,
)

VALID_STATUSES = {"PENDING", "APPROVED", "REJECTED", "CANCELLED"}

@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.skip_db_init:
        await initialize_database()
    yield

app = FastAPI(title="Employee Workflow API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/workflows/health")
async def health():
    return {"service": "employee-workflow-api", "status": "healthy"}

@app.get(
    "/api/workflows/leaves",
    response_model=list[LeaveOut],
)
async def list_leaves(
    employee_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(get_current_user),
):
    statement = select(LeaveRequest).order_by(
        LeaveRequest.created_at.desc()
    )

    if employee_id is not None:
        statement = statement.where(
            LeaveRequest.employee_id == employee_id
        )

    result = await session.scalars(statement)

    return list(result)

@app.post(
    "/api/workflows/leaves",
    response_model=LeaveOut,
    status_code=201,
)
async def create_leave(
    payload: LeaveCreate,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(
        require_roles(
            "EMPLOYEE",
            "MANAGER",
            "ADMIN",
        )
    ),
):
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date")

    leave = LeaveRequest(**payload.model_dump(), status="PENDING")
    session.add(leave)
    await session.flush()

    notification = Notification(
        employee_id=payload.manager_id,
        event_type="LEAVE_REQUEST_CREATED",
        message=f"New leave request #{leave.id} from employee {payload.employee_id}",
    )
    session.add(notification)
    await session.commit()
    await session.refresh(leave)

    await manager.send(
        payload.manager_id,
        {
            "type": "LEAVE_REQUEST_CREATED",
            "message": notification.message,
            "entity_id": leave.id,
        },
    )
    return leave

@app.patch(
    "/api/workflows/leaves/{leave_id}/status",
    response_model=LeaveOut,
)
async def update_leave_status(
    leave_id: int,
    payload: LeaveStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(
        require_roles(
            "MANAGER",
            "ADMIN",
        )
    ),
):
    new_status = payload.status.upper()
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of {sorted(VALID_STATUSES)}")

    leave = await session.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave request not found")

    leave.status = new_status
    notification = Notification(
        employee_id=leave.employee_id,
        event_type="LEAVE_STATUS_CHANGED",
        message=f"Leave request #{leave.id} changed to {new_status}",
    )
    session.add(notification)
    await session.commit()
    await session.refresh(leave)

    await manager.send(
        leave.employee_id,
        {
            "type": "LEAVE_STATUS_CHANGED",
            "message": notification.message,
            "entity_id": leave.id,
        },
    )
    return leave

@app.get(
    "/api/workflows/notifications/{employee_id}",
    response_model=list[NotificationOut],
)
async def list_notifications(
    employee_id: int,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(get_current_user),
):
    result = await session.scalars(
        select(Notification)
        .where(Notification.employee_id == employee_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    return list(result)

@app.get("/api/workflows/internal/config-check")
async def internal_config_check(x_internal_api_key: str = Header(alias="X-Internal-API-Key")):
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid internal API key")
    return {"secret_injection": "working"}

@app.websocket("/ws/notifications/{employee_id}")
async def notifications_websocket(
    websocket: WebSocket,
    employee_id: int,
):
    await websocket.accept()

    registered = False

    try:
        first_message = await websocket.receive_json()

        token = first_message.get("access_token")

        if not token:
            await websocket.close(code=4401)
            return

        decode_access_token(token)

        manager.register(employee_id, websocket)
        registered = True

        await websocket.send_json({
            "type": "AUTH_OK",
            "message": "WebSocket authenticated",
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    except Exception:
        await websocket.close(code=4401)

    finally:
        if registered:
            manager.disconnect(
                employee_id,
                websocket,
            )
