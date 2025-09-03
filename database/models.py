from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    BigInteger,
    Integer,
    ForeignKey,
    DateTime,
    String,
    Boolean,
    Text,
    JSON,
)

from configuration.config_db import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id"), nullable=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctors.id"), nullable=True
    )
    procedure_id: Mapped[int | None] = mapped_column(
        ForeignKey("procedures.id"), nullable=True
    )
    start_time: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)

    client: Mapped["Client"] = relationship("Client", back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="appointments")
    procedure: Mapped["Procedure"] = relationship(
        "Procedure", back_populates="appointments"
    )


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    passport: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    stage: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    id_crm: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    survey_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    surveys_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Связи
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="client"
    )
    patient_questions: Mapped[list["PatientQuestion"]] = relationship(
        "PatientQuestion", back_populates="patient"
    )
    user_scenarios: Mapped[list["UserScenario"]] = relationship(
        "UserScenario", back_populates="client"
    )


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str] = mapped_column(String(100), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    id_crm: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Связи
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="doctor"
    )


class PatientQuestion(Base):
    __tablename__ = "patient_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    patient_tg_id: Mapped[int] = mapped_column(
        ForeignKey("clients.tg_id"), nullable=False
    )
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    support_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связи
    patient: Mapped["Client"] = relationship(
        "Client", back_populates="patient_questions"
    )


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    id_group: Mapped[int] = mapped_column(Integer, nullable=False)
    art: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Связи
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="procedure"
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        "Scenario", back_populates="procedure"
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stage: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scenarios_msg: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    procedure_id: Mapped[int | None] = mapped_column(
        ForeignKey("procedures.id"), nullable=True
    )

    # Связи
    procedure: Mapped["Procedure"] = relationship(
        "Procedure", back_populates="scenarios"
    )


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    file: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class UserScenario(Base):
    __tablename__ = "users_scenarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scenarios: Mapped[dict] = mapped_column(JSON, nullable=False)
    stage_msg: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clients_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.tg_id"), nullable=True
    )

    # Связи
    client: Mapped["Client"] = relationship("Client", back_populates="user_scenarios")


class Video(Base):
    __tablename__ = "video"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_link: Mapped[str] = mapped_column(Text, nullable=False)
    for_scenarios: Mapped[str | None] = mapped_column(Text, nullable=True)
