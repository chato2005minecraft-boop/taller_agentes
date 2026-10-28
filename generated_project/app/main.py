from typing import Optional
from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Empleado,
    EmpleadoCreate,
    EmpleadoResponse,
    RevisionRequest,
    SaldoResponse,
    SolicitudCreate,
    SolicitudResponse,
    SolicitudVacaciones,
    engine,
    get_db,
)

app = FastAPI(title="TalentCore API")
Base.metadata.create_all(bind=engine)


def calcular_saldo(emp: Empleado, db: Session) -> tuple[int, int, int]:
    dias_totales = 12 if emp.anios_antiguedad < 1 else min(12 + 2 * (emp.anios_antiguedad - 1), 20)
    dias_aprobados = (
        db.query(func.coalesce(func.sum(SolicitudVacaciones.dias_solicitados), 0))
        .filter(
            SolicitudVacaciones.empleado_id == emp.id,
            SolicitudVacaciones.estado == "APPROVED",
        )
        .scalar()
    )
    saldo_disponible = dias_totales - dias_aprobados
    return dias_totales, dias_aprobados, saldo_disponible


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "ok"}


@app.post("/api/v1/empleados", status_code=status.HTTP_201_CREATED, response_model=EmpleadoResponse)
def crear_empleado(
    payload: EmpleadoCreate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    if db.query(Empleado).count() > 0:
        if x_user_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Header X-User-Id required")
        admin = db.query(Empleado).filter(Empleado.id == x_user_id).first()
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if admin.rol != "ADMIN_RRHH":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN_RRHH can create employees")

    empleado = Empleado(**payload.model_dump())
    db.add(empleado)
    db.commit()
    db.refresh(empleado)
    return empleado


@app.get("/api/v1/vacaciones/saldo/{empleado_id}", response_model=SaldoResponse)
def obtener_saldo(empleado_id: int, db: Session = Depends(get_db)):
    emp = db.query(Empleado).filter(Empleado.id == empleado_id).first()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado not found")
    dias_totales, dias_aprobados, saldo_disponible = calcular_saldo(emp, db)
    return SaldoResponse(
        empleado_id=emp.id,
        dias_totales=dias_totales,
        dias_aprobados=dias_aprobados,
        saldo_disponible=saldo_disponible,
    )


@app.post("/api/v1/vacaciones/solicitar", status_code=status.HTTP_201_CREATED, response_model=SolicitudResponse)
def solicitar_vacaciones(payload: SolicitudCreate, db: Session = Depends(get_db)):
    emp = db.query(Empleado).filter(Empleado.id == payload.empleado_id).first()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado not found")

    _, _, saldo_disponible = calcular_saldo(emp, db)
    if payload.dias_solicitados > saldo_disponible:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient vacation balance")

    solicitud = SolicitudVacaciones(
        empleado_id=payload.empleado_id,
        dias_solicitados=payload.dias_solicitados,
        motivo=payload.motivo,
        estado="PENDING",
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    return solicitud


@app.post("/api/v1/vacaciones/{solicitud_id}/revisar", status_code=status.HTTP_200_OK, response_model=SolicitudResponse)
def revisar_solicitud(
    solicitud_id: int,
    payload: RevisionRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    solicitud = db.query(SolicitudVacaciones).filter(SolicitudVacaciones.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud not found")

    manager = db.query(Empleado).filter(Empleado.id == x_user_id).first()
    if not manager:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found")

    empleado = db.query(Empleado).filter(Empleado.id == solicitud.empleado_id).first()
    if not empleado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado not found")

    if manager.rol != "MANAGER" or empleado.manager_id != x_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized: Not the direct manager")

    if solicitud.estado != "PENDING":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already processed")

    if payload.accion == "APPROVE":
        solicitud.estado = "APPROVED"
    elif payload.accion == "REJECT":
        solicitud.estado = "REJECTED"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")

    solicitud.revisado_por_id = x_user_id
    db.commit()
    db.refresh(solicitud)
    return solicitud
