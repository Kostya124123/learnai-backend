from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="indexed")  # indexed | error
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime, server_default=func.now())
    chunk_count = Column(Integer, default=0)
