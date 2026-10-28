import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Base, engine


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ac01_solicitud_valida_y_calculo_saldo(client):
    # 1. Crear ADMIN_RRHH (primer empleado del sistema, sin auth requerida)
    admin_payload = {
        "nombre": "Admin User",
        "email": "admin@talentcore.com",
        "rol": "ADMIN_RRHH",
        "anios_antiguedad": 5,
        "manager_id": None,
    }
    res_admin = client.post("/api/v1/empleados", json=admin_payload)
    assert res_admin.status_code == 201
    assert res_admin.json()["id"] == 1

    headers_admin = {"X-User-Id": "1"}

    # 2. Crear MANAGER (id=2)
    manager_payload = {
        "nombre": "Manager One",
        "email": "manager1@talentcore.com",
        "rol": "MANAGER",
        "anios_antiguedad": 4,
        "manager_id": None,
    }
    res_manager = client.post("/api/v1/empleados", json=manager_payload, headers=headers_admin)
    assert res_manager.status_code == 201
    assert res_manager.json()["id"] == 2

    # 3. Crear EMPLEADO (id=3, anios_antiguedad=3, manager_id=2)
    emp_payload = {
        "nombre": "Employee One",
        "email": "emp1@talentcore.com",
        "rol": "EMPLEADO",
        "anios_antiguedad": 3,
        "manager_id": 2,
    }
    res_emp = client.post("/api/v1/empleados", json=emp_payload, headers=headers_admin)
    assert res_emp.status_code == 201
    assert res_emp.json()["id"] == 3

    # 4. Validar saldo inicial: anios=3 -> min(12 + 2*(3-1), 20) = 16 días
    res_saldo = client.get("/api/v1/vacaciones/saldo/3")
    assert res_saldo.status_code == 200
    saldo_data = res_saldo.json()
    assert saldo_data["dias_totales"] == 16
    assert saldo_data["saldo_disponible"] == 16
    assert saldo_data["dias_aprobados"] == 0

    # 5. Solicitar 5 días
    solicitud_payload = {
        "empleado_id": 3,
        "dias_solicitados": 5,
        "motivo": "Vacaciones de verano",
    }
    res_solicitud = client.post("/api/v1/vacaciones/solicitar", json=solicitud_payload)
    assert res_solicitud.status_code == 201
    solicitud_data = res_solicitud.json()
    assert solicitud_data["id"] == 1
    assert solicitud_data["estado"] == "PENDING"
    assert solicitud_data["dias_solicitados"] == 5

    # 6. Manager aprueba la solicitud
    headers_manager = {"X-User-Id": "2"}
    revision_payload = {"accion": "APPROVE"}
    res_revision = client.post("/api/v1/vacaciones/1/revisar", json=revision_payload, headers=headers_manager)
    assert res_revision.status_code == 200
    assert res_revision.json()["estado"] == "APPROVED"
    assert res_revision.json()["revisado_por_id"] == 2

    # 7. Validar saldo actualizado: 16 - 5 = 11 días disponibles
    res_saldo_post = client.get("/api/v1/vacaciones/saldo/3")
    assert res_saldo_post.status_code == 200
    saldo_post_data = res_saldo_post.json()
    assert saldo_post_data["dias_totales"] == 16
    assert saldo_post_data["dias_aprobados"] == 5
    assert saldo_post_data["saldo_disponible"] == 11


def test_ac02_saldo_insuficiente(client):
    # 1. Crear ADMIN_RRHH (id=1)
    admin_payload = {
        "nombre": "Admin User",
        "email": "admin@talentcore.com",
        "rol": "ADMIN_RRHH",
        "anios_antiguedad": 2,
        "manager_id": None,
    }
    res_admin = client.post("/api/v1/empleados", json=admin_payload)
    assert res_admin.status_code == 201

    # 2. Crear EMPLEADO (id=2, anios_antiguedad=1 -> saldo_disponible=12)
    emp_payload = {
        "nombre": "Junior Employee",
        "email": "junior@talentcore.com",
        "rol": "EMPLEADO",
        "anios_antiguedad": 1,
        "manager_id": None,
    }
    res_emp = client.post("/api/v1/empleados", json=emp_payload, headers={"X-User-Id": "1"})
    assert res_emp.status_code == 201
    assert res_emp.json()["id"] == 2

    # 3. Solicitar 15 días (supera saldo disponible de 12)
    solicitud_payload = {
        "empleado_id": 2,
        "dias_solicitados": 15,
        "motivo": "Viaje largo",
    }
    response = client.post("/api/v1/vacaciones/solicitar", json=solicitud_payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient vacation balance"


def test_ac03_manager_no_autorizado(client):
    # 1. Crear ADMIN_RRHH (id=1)
    admin_payload = {
        "nombre": "Admin User",
        "email": "admin@talentcore.com",
        "rol": "ADMIN_RRHH",
        "anios_antiguedad": 5,
        "manager_id": None,
    }
    client.post("/api/v1/empleados", json=admin_payload)
    headers_admin = {"X-User-Id": "1"}

    # 2. Crear MANAGER A (id=2)
    manager_a = {
        "nombre": "Manager A",
        "email": "manager_a@talentcore.com",
        "rol": "MANAGER",
        "anios_antiguedad": 3,
        "manager_id": None,
    }
    res_a = client.post("/api/v1/empleados", json=manager_a, headers=headers_admin)
    assert res_a.json()["id"] == 2

    # 3. Crear MANAGER B (id=3)
    manager_b = {
        "nombre": "Manager B",
        "email": "manager_b@talentcore.com",
        "rol": "MANAGER",
        "anios_antiguedad": 3,
        "manager_id": None,
    }
    res_b = client.post("/api/v1/empleados", json=manager_b, headers=headers_admin)
    assert res_b.json()["id"] == 3

    # 4. Crear EMPLEADO con manager_id=2 (id=4)
    empleado = {
        "nombre": "Direct Report of A",
        "email": "report_a@talentcore.com",
        "rol": "EMPLEADO",
        "anios_antiguedad": 1,
        "manager_id": 2,
    }
    res_emp = client.post("/api/v1/empleados", json=empleado, headers=headers_admin)
    assert res_emp.json()["id"] == 4

    # 5. Empleado 4 solicita 3 días
    solicitud_payload = {
        "empleado_id": 4,
        "dias_solicitados": 3,
        "motivo": "Asunto personal",
    }
    res_solicitud = client.post("/api/v1/vacaciones/solicitar", json=solicitud_payload)
    assert res_solicitud.status_code == 201
    assert res_solicitud.json()["id"] == 1

    # 6. MANAGER B (id=3) intenta revisar la solicitud
    res_revision = client.post(
        "/api/v1/vacaciones/1/revisar",
        json={"accion": "APPROVE"},
        headers={"X-User-Id": "3"},
    )
    assert res_revision.status_code == 403
    assert res_revision.json()["detail"] == "Unauthorized: Not the direct manager"
