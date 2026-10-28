import sqlite3
import sys
import uuid
from pathlib import Path

import httpx


BASE_URL = "http://127.0.0.1:8000"


def obtener_admin_local():
    database_path = Path(__file__).with_name("talentcore.db")
    if not database_path.exists():
        return None

    database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        row = connection.execute(
            "SELECT id FROM empleados WHERE rol = ? ORDER BY id LIMIT 1",
            ("ADMIN_RRHH",),
        ).fetchone()
    return row[0] if row else None


def imprimir_paso(titulo, estado, detalle=""):
    color = "\033[92m[EXITO]\033[0m" if estado else "\033[91m[FALLO]\033[0m"
    print(f"{color} {titulo}")
    if detalle:
        print(f"       -> {detalle}")
    return estado


def ejecutar_auditoria():
    print("=" * 70)
    print("   INICIANDO BATERÍA DE PRUEBAS DINÁMICAS (CLIENTE HTTP)")
    print("=" * 70)
    exitos = True
    sufijo = uuid.uuid4().hex

    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        # 1. Health Check
        respuesta = client.get("/health")
        exitos &= imprimir_paso(
            "1. Verificación de servicio (/health)",
            respuesta.status_code == 200,
            respuesta.json(),
        )

        # 2. Crear Admin inicial (sin header)
        admin_data = {
            "nombre": "Super Admin",
            "email": f"admin_{sufijo}@corp.com",
            "rol": "ADMIN_RRHH",
            "anios_antiguedad": 5,
        }
        respuesta = client.post("/api/v1/empleados", json=admin_data)
        admin_id = respuesta.json().get("id")
        detalle_admin = f"Admin ID asignado: {admin_id}"
        if respuesta.status_code == 403:
            admin_id = obtener_admin_local()
            if admin_id is not None:
                respuesta_status = 201
                detalle_admin = f"Se reutiliza el Admin local existente (ID: {admin_id})"
            else:
                respuesta_status = respuesta.status_code
                detalle_admin = (
                    f"{respuesta.json()}. No se encontró un ADMIN_RRHH en "
                    "generated_project/talentcore.db."
                )
        else:
            respuesta_status = respuesta.status_code
            if respuesta_status != 201:
                detalle_admin = respuesta.json()
        exitos &= imprimir_paso(
            "2. Registro del primer Administrador",
            respuesta_status == 201,
            detalle_admin,
        )
        if respuesta_status != 201:
            return False

        # 3. Crear Manager
        headers_admin = {"X-User-Id": str(admin_id)}
        manager_data = {
            "nombre": "Jefe de Operaciones",
            "email": f"jefe_{sufijo}@corp.com",
            "rol": "MANAGER",
            "anios_antiguedad": 4,
        }
        respuesta = client.post(
            "/api/v1/empleados",
            json=manager_data,
            headers=headers_admin,
        )
        manager_id = respuesta.json().get("id")
        exitos &= imprimir_paso(
            "3. Registro de Manager",
            respuesta.status_code == 201,
            (
                f"Manager ID: {manager_id}"
                if respuesta.status_code == 201
                else respuesta.json()
            ),
        )
        if respuesta.status_code != 201:
            return False

        # 4. Crear Empleado subordinado
        empleado_data = {
            "nombre": "Ana Desarrolladora",
            "email": f"ana_{sufijo}@corp.com",
            "rol": "EMPLEADO",
            "anios_antiguedad": 2,  # 12 + 2*(2-1) = 14 días
            "manager_id": manager_id,
        }
        respuesta = client.post(
            "/api/v1/empleados",
            json=empleado_data,
            headers=headers_admin,
        )
        empleado_id = respuesta.json().get("id")
        exitos &= imprimir_paso(
            "4. Registro de Empleado (2 años antigüedad)",
            respuesta.status_code == 201,
            (
                f"Empleado ID: {empleado_id}"
                if respuesta.status_code == 201
                else respuesta.json()
            ),
        )
        if respuesta.status_code != 201:
            return False

        # 5. Consultar saldo inicial
        respuesta = client.get(f"/api/v1/vacaciones/saldo/{empleado_id}")
        saldo = respuesta.json()
        exitos &= imprimir_paso(
            "5. Verificación de cálculo legal (14 días)",
            saldo.get("saldo_disponible") == 14,
            saldo,
        )

        # 6. Intento de solicitud con exceso de días (debe fallar con 400)
        solicitud_exceso = {
            "empleado_id": empleado_id,
            "dias_solicitados": 15,
            "motivo": "Exceso",
        }
        respuesta = client.post(
            "/api/v1/vacaciones/solicitar",
            json=solicitud_exceso,
        )
        exitos &= imprimir_paso(
            "6. Intento de pedir 15 días (Excede saldo)",
            respuesta.status_code == 400,
            respuesta.json(),
        )

        # 7. Solicitud válida de 4 días
        solicitud_valida = {
            "empleado_id": empleado_id,
            "dias_solicitados": 4,
            "motivo": "Viaje corto",
        }
        respuesta = client.post(
            "/api/v1/vacaciones/solicitar",
            json=solicitud_valida,
        )
        solicitud_id = respuesta.json().get("id")
        exitos &= imprimir_paso(
            "7. Solicitud válida de 4 días (PENDING)",
            respuesta.status_code == 201,
            (
                f"Solicitud ID: {solicitud_id}"
                if respuesta.status_code == 201
                else respuesta.json()
            ),
        )
        if respuesta.status_code != 201:
            return False

        # 8. Intento de aprobación por usurpador (debe fallar con 403)
        headers_usurpador = {"X-User-Id": "999"}
        respuesta = client.post(
            f"/api/v1/vacaciones/{solicitud_id}/revisar",
            json={"accion": "APPROVE"},
            headers=headers_usurpador,
        )
        exitos &= imprimir_paso(
            "8. Seguridad BOLA: Intento de aprobación por usuario no autorizado",
            respuesta.status_code in (403, 404),
            respuesta.json(),
        )

        # 9. Aprobación oficial por el jefe directo
        headers_manager = {"X-User-Id": str(manager_id)}
        respuesta = client.post(
            f"/api/v1/vacaciones/{solicitud_id}/revisar",
            json={"accion": "APPROVE"},
            headers=headers_manager,
        )
        exitos &= imprimir_paso(
            "9. Aprobación oficial por su Manager directo",
            respuesta.status_code == 200,
            respuesta.json(),
        )

        # 10. Saldo final descontado
        respuesta = client.get(f"/api/v1/vacaciones/saldo/{empleado_id}")
        saldo_final = respuesta.json()
        exitos &= imprimir_paso(
            "10. Balance final de vacaciones (14 - 4 = 10 días)",
            saldo_final.get("saldo_disponible") == 10,
            saldo_final,
        )

    print("=" * 70)
    if exitos:
        print("   BATERÍA DE PRUEBAS COMPLETADA EXITOSAMENTE")
    else:
        print("   BATERÍA DE PRUEBAS COMPLETADA CON ERRORES")
    print("=" * 70)
    return exitos


if __name__ == "__main__":
    try:
        if not ejecutar_auditoria():
            sys.exit(1)
    except httpx.RequestError as error:
        print(f"\n[ERROR] No se pudo completar la solicitud HTTP: {error}")
        sys.exit(1)
