from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base

class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int]= mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str]= mapped_column(String(255), nullable=False, index=True)
    address: Mapped[str | None]= mapped_column(String(255), nullable=False)
    city: Mapped[str | None]= mapped_column(String(100), nullable=True, index=True)
    state: Mapped[str | None]= mapped_column(String(100), nullable=True, index=True)
    country: Mapped[str | None]= mapped_column(String(100), nullable=True)
    unit_count: Mapped[int | None]= mapped_column(Integer, nullable=True)
    description: Mapped[str | None]= mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )