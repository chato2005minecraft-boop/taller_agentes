# ARCHITECTURE.md: TalentCore API

## 1. MODELO DE DATOS (SQLite / SQLAlchemy)

```python
from sqlalchemy import Column, Integer, String, ForeignKey, CheckConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Empleado(Base):
    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    rol = Column(String, nullable=False)  # 'EMPLEADO', 'MANAGER', 'ADMIN_RRHH'
    anios_antiguedad = Column(Integer, nullable=False, default=1)
    manager_id = Column(Integer, ForeignKey("empleados.id"), nullable=True)

class SolicitudVacaciones(Base):
    __tablename__ = "solicitudes_vacaciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    empleado_id = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    dias_solicitados = Column(Integer, nullable=False)
    motivo = Column(String, nullable=True)
    estado = Column(String, nullable=False, default="PENDING")  # 'PENDING', 'APPROVED', 'REJECTED'
    revisado_por_id = Column(Integer, ForeignKey("empleados.id"), nullable=True)

    __table_args__ = (
        CheckConstraint("dias_solicitados > 0", name="check_dias_positivos"),
    )
```

## 2. ESQUEMAS PYDANTIC V2

```python
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

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
```

## 3. ENDPOINTS REST Y RBAC

Dependencia global de autenticación: `X-User-Id: int = Header(...)`. Valida existencia en BD; si no existe, retorna `HTTP 404 Not Found`.

| Método | Endpoint | Auth | RBAC / Reglas de Negocio | Respuesta |
|---|---|---|---|---|
| `GET` | `/health` | No | Público. Retorna disponibilidad del servicio. | `200 OK` `{"status": "ok"}` |
| `POST` | `/api/v1/empleados` | Condicional | Si `empleados` está vacía, permite crear el primer `ADMIN_RRHH` sin header. Si ya existen registros, requiere `X-User-Id` con rol `ADMIN_RRHH` (sino `403 Forbidden`). | `201 Created` (`EmpleadoResponse`) |
| `GET` | `/api/v1/vacaciones/saldo/{empleado_id}` | Sí | Calcula:<br>1. `dias_totales = min(12 + 2 * max(anios_antiguedad - 1, 0), 20)`<br>2. `dias_aprobados = sum(dias_solicitados)` con `estado == 'APPROVED'`<br>3. `saldo_disponible = dias_totales - dias_aprobados` | `200 OK` (`SaldoResponse`) |
| `POST` | `/api/v1/vacaciones/solicitar` | Sí | Valida que `dias_solicitados <= saldo_disponible`. Si excede, retorna `400 Bad Request` (`detail="Insufficient vacation balance"`). Crea registro con estado `PENDING`. | `201 Created` (`SolicitudResponse`) |
| `POST` | `/api/v1/vacaciones/{solicitud_id}/revisar` | Sí | Requiere rol `MANAGER` y `empleado.manager_id == X-User-Id`. Si falla, retorna `403 Forbidden` (`detail="Unauthorized: Not the direct manager"`). Si la solicitud no está en `PENDING`, retorna `400 Bad Request`. Transiciona a `APPROVED` (si `accion == 'APPROVE'`) o `REJECTED` (si `accion == 'REJECT'`) y fija `revisado_por_id = X-User-Id`. | `200 OK` (`SolicitudResponse`) |