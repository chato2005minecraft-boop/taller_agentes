from typing import Generator, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./talentcore.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Empleado(Base):
    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    rol = Column(String, nullable=False)
    anios_antiguedad = Column(Integer, nullable=False, default=1)
    manager_id = Column(Integer, ForeignKey("empleados.id"), nullable=True)


class SolicitudVacaciones(Base):
    __tablename__ = "solicitudes_vacaciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    empleado_id = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    dias_solicitados = Column(Integer, nullable=False)
    motivo = Column(String, nullable=True)
    estado = Column(String, nullable=False, default="PENDING")
    revisado_por_id = Column(Integer, ForeignKey("empleados.id"), nullable=True)

    __table_args__ = (
        CheckConstraint("dias_solicitados > 0", name="check_dias_positivos"),
    )


class EmpleadoCreate(BaseModel):
    nombre: str
    email: str
    rol: Literal["EMPLEADO", "MANAGER", "ADMIN_RRHH"]
    anios_antiguedad: int = Field(default=1, ge=0)
    manager_id: Optional[int] = None


class EmpleadoResponse(EmpleadoCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SaldoResponse(BaseModel):
    empleado_id: int
    dias_totales: int
    dias_aprobados: int
    saldo_disponible: int


class SolicitudCreate(BaseModel):
    empleado_id: int
    dias_solicitados: int = Field(gt=0)
    motivo: Optional[str] = None


class RevisionRequest(BaseModel):
    accion: Literal["APPROVE", "REJECT"]


class SolicitudResponse(BaseModel):
    id: int
    empleado_id: int
    dias_solicitados: int
    motivo: Optional[str]
    estado: Literal["PENDING", "APPROVED", "REJECTED"]
    revisado_por_id: Optional[int]
    model_config = ConfigDict(from_attributes=True)
