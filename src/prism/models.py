from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repo: Mapped[str]
    pr_number: Mapped[int]
    diff_type: Mapped[str]
    reasoning: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    comments: Mapped[list["Comment"]] = relationship(back_populates="review")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"))
    filename: Mapped[str]
    line: Mapped[int]
    comment: Mapped[str]
    severity: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    review: Mapped["Review"] = relationship(back_populates="comments")
