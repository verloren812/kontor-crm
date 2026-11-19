import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from enums import ClientStatus, DealStage, Role

# --- Users ---

# bcrypt only looks at the first 72 bytes of a password and silently drops the
# rest, so two long passwords with the same beginning would be the same password.
# Bytes, not characters: non-ASCII letters take 2+ bytes in UTF-8.
BCRYPT_MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8


class UserCreate(BaseModel):
    # use_enum_values: model_dump() returns "manager", not Role.MANAGER.
    # validate_default: the default value goes through the same conversion.
    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    # The admin chooses the role. Default is the least privileged one.
    role: Role = Role.MANAGER

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return value

    @field_validator("password")
    @classmethod
    def _check_password_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password is longer than {BCRYPT_MAX_PASSWORD_BYTES} bytes; bcrypt would ignore the rest"
            )
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    created_at: datetime


class UserRoleUpdate(BaseModel):
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str


# --- Clients ---

_PHONE_SEPARATORS = re.compile(r"[\s\-()./]")
_PHONE_FORMAT = re.compile(r"^\+?\d{6,15}$")  # E.164 allows at most 15 digits


def normalize_phone(value: str) -> str:
    """
    Bring a phone number to one canonical form.

    "+49 176 1234-567", "+49 (176) 1234567" and "0049 1761234567" are the same
    number. Without normalization the UNIQUE constraint treats them as three
    different values and the duplicate check does nothing.
    """
    value = _PHONE_SEPARATORS.sub("", value.strip())
    if value.startswith("00"):
        value = "+" + value[2:]
    if not _PHONE_FORMAT.match(value):
        raise ValueError("Phone number must contain 6 to 15 digits, optionally starting with +")
    return value


def _empty_to_none(value):
    """Treat "" as "no email" instead of failing email validation."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


class ClientCreate(BaseModel):
    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(max_length=32)
    email: Optional[EmailStr] = None
    status: ClientStatus = ClientStatus.NEW

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, value):
        return _empty_to_none(value)


class ClientUpdate(BaseModel):
    """Partial update: every field is optional."""

    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[EmailStr] = None
    status: Optional[ClientStatus] = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else normalize_phone(value)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, value):
        return _empty_to_none(value)


class ClientUpdateStatus(BaseModel):
    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    status: ClientStatus


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    email: Optional[str]
    status: str
    owner_id: Optional[int]
    created_at: datetime
    updated_at: datetime


# --- Deals ---

# Amounts are accepted and stored as Decimal. max_digits/decimal_places match
# NUMERIC(12, 2), so extra digits are rejected on input instead of being lost
# silently on write.
MONEY_FIELD = Field(ge=0, max_digits=12, decimal_places=2)


class DealCreate(BaseModel):
    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    title: str = Field(min_length=1, max_length=200)
    amount: Decimal = MONEY_FIELD
    stage: DealStage = DealStage.NEW
    client_id: int


class DealUpdate(BaseModel):
    """Partial update of a deal."""

    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    amount: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    stage: Optional[DealStage] = None


class DealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    amount: float
    stage: str
    client_id: int
    client_name: Optional[str] = None
    owner_id: Optional[int]
    owner_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StageChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_stage: Optional[str]
    to_stage: str
    changed_at: datetime
    changed_by_id: Optional[int]
    changed_by_name: Optional[str] = None


# --- Tasks ---

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    due_date: Optional[datetime] = None
    deal_id: int


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    due_date: Optional[datetime] = None
    is_done: Optional[bool] = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    is_done: bool
    deal_id: int
    deal_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# --- Analytics ---

class StageSummary(BaseModel):
    stage: str
    count: int
    total_amount: float
    is_won: bool = False
    is_closed: bool = False


class ManagerSummary(BaseModel):
    manager_id: Optional[int]
    username: str
    deals_count: int
    total_amount: float
    won_amount: float = 0.0


class DashboardResponse(BaseModel):
    deals_by_stage: list[StageSummary]
    total_deals_count: int
    total_amount: float
    open_amount: float = 0.0        # value of the pipeline that is still open
    won_amount: float = 0.0
    win_rate: Optional[float] = None  # won / closed deals; None while nothing is closed
    clients_count: int = 0
    overdue_tasks: list[TaskResponse]  # capped, see overdue_total
    overdue_total: int = 0
    upcoming_tasks: list[TaskResponse]
    revenue_by_manager: Optional[list[ManagerSummary]] = None  # admin only
