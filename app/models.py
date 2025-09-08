from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, Date, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Forklift(Base):
    __tablename__ = "forklifts"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String, nullable=False)
    type = Column(String, nullable=False)
    eq_no = Column(String, nullable=False, unique=True)
    serial_number = Column(String, nullable=False, unique=True)
    location = Column(String, nullable=False)
    powertrain = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    mfg_year = Column(Integer, nullable=False)
    status = Column(String, nullable=False)

    pm_jobs = relationship("PMJob", back_populates="forklift",
                           cascade="all, delete-orphan", passive_deletes=True)
    workshop_jobs = relationship("WorkshopJob", back_populates="forklift",
                                 cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint('eq_no', name='uq_eq_no'),
        UniqueConstraint('serial_number', name='uq_serial_number'),
    )


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True)
    password = Column(String, nullable=True)
    role = Column(String, nullable=False, default="teknisi")  # admin / supervisor / teknisi


class PMJob(Base):
    __tablename__ = "pm_jobs"
    id = Column(Integer, primary_key=True, index=True)
    forklift_id = Column(Integer, ForeignKey("forklifts.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    report_no = Column(String, nullable=False)
    job_desc = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    next_pm_date = Column(Date, nullable=True)
    created_by = Column(Integer, nullable=False)  # sementara int user id

    forklift = relationship("Forklift", back_populates="pm_jobs")
    assigned = relationship("PMJobAssignment", back_populates="pm_job",
                            cascade="all, delete-orphan", passive_deletes=True)


class PMJobAssignment(Base):
    __tablename__ = "pm_job_assignments"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("pm_jobs.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id"))

    pm_job = relationship("PMJob", back_populates="assigned")
    user = relationship("User")


class WorkshopJob(Base):
    __tablename__ = "workshop_jobs"

    id = Column(Integer, primary_key=True, index=True)
    forklift_id = Column(Integer, ForeignKey("forklifts.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    report_no = Column(String, nullable=False)
    job_desc = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)

    forklift = relationship("Forklift", back_populates="workshop_jobs")
    assigned = relationship("WorkshopJobAssignment", back_populates="workshop_job",
                            cascade="all, delete-orphan", passive_deletes=True)
    items = relationship("WorkshopJobItem", back_populates="workshop_job",
                         cascade="all, delete-orphan", passive_deletes=True)


class WorkshopJobAssignment(Base):
    __tablename__ = "workshop_job_assignments"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("workshop_jobs.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id"))

    workshop_job = relationship("WorkshopJob", back_populates="assigned")
    user = relationship("User")


class WorkshopJobItem(Base):
    __tablename__ = "workshop_job_items"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("workshop_jobs.id", ondelete="CASCADE"))
    item_name = Column(String, nullable=False)
    qty = Column(Integer, nullable=False)

    workshop_job = relationship("WorkshopJob", back_populates="items")
