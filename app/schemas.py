from datetime import date, datetime
from pydantic import BaseModel, ConfigDict

class LeaveCreate(BaseModel):
    employee_id: int
    manager_id: int
    leave_type: str
    start_date: date
    end_date: date
    reason: str

class LeaveOut(LeaveCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: datetime

class LeaveStatusUpdate(BaseModel):
    status: str

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    event_type: str
    message: str
    created_at: datetime
