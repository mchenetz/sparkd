from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Box(Base):
    __tablename__ = "boxes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    host: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(default=22)
    user: Mapped[str] = mapped_column(String)
    ssh_key_path: Mapped[str | None] = mapped_column(String, nullable=True)
    use_agent: Mapped[bool] = mapped_column(default=True)
    repo_path: Mapped[str] = mapped_column(default="~/spark-vllm-docker")
    tags_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    capabilities_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    capabilities_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    launches: Mapped[list["Launch"]] = relationship(back_populates="box")


class Launch(Base):
    __tablename__ = "launches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    box_id: Mapped[str] = mapped_column(ForeignKey("boxes.id"))
    recipe_name: Mapped[str] = mapped_column(String)
    recipe_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    mods_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String)  # starting|healthy|failed|stopped|interrupted
    container_id: Mapped[str | None] = mapped_column(String, nullable=True)
    command: Mapped[str] = mapped_column(String)
    log_path: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_info_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    box: Mapped[Box] = relationship(back_populates="launches")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    actor: Mapped[str] = mapped_column(String, default="local")
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
