# PRD: TalentCore API

### 1. ROLES DEL SISTEMA
* **EMPLEADO**: Autenticado. Consulta su propio saldo de vacaciones y crea solicitudes de días libres exclusivamente para su cuenta (`empleado_id == current_user.id`).
* **MANAGER**: Autenticado. Aprueba o rechaza solicitudes de vacaciones única y estrictamente si es el jefe directo del solicitante (`solicitud.empleado.manager_id == current_user.id`).
* **ADMIN_RRHH**: Autenticado. Registra nuevos empleados en el sistema y asigna su respectivo `manager_id`.

### 2. REGLA DE SALDO DE VACACIONES
* **Días Totales Otorgados**:
  * Si `anios_antiguedad < 1`: `dias_totales = 12`
  * Si `anios_antiguedad >= 1`: `dias_totales = min(12 + 2 * (anios_antiguedad - 1), 20)`
* **Saldo Disponible**:
  $$\text{saldo\_disponible} = \text{dias\_totales} - \sum(\text{dias\_solicitados}_{[\text{estado} = \text{'APPROVED'}]})$$
* **Restricción**: `dias_solicitados <= saldo_disponible`.

### 3. MÁQUINA DE ESTADOS DE SOLICITUD
* **Estados**: `PENDING`, `APPROVED`, `REJECTED`.
* **Transiciones y Reglas**:
  * `[Crear Solicitud]` $\rightarrow$ `PENDING` (estado inicial).
  * `PENDING` $\rightarrow$ `APPROVED` (descuenta días del saldo disponible; estado terminal).
  * `PENDING` $\rightarrow$ `REJECTED` (no altera el saldo; estado terminal).
  * Modificaciones o transiciones desde estados distintos a `PENDING` deben responder `422 Unprocessable Entity`.

### 4. CRITERIOS DE ACEPTACIÓN

```gherkin
Feature: Gestión de Vacaciones TalentCore

  Scenario: AC-01 Solicitud válida con saldo suficiente
    Given un EMPLEADO con saldo_disponible de 12 días
    When envía un POST /vacaciones solicitando 5 días
    Then el sistema responde HTTP 201 Created
    And la solicitud queda persistida con estado "PENDING"

  Scenario: AC-02 Solicitud rechazada por saldo insuficiente
    Given un EMPLEADO con saldo_disponible de 4 días
    When envía un POST /vacaciones solicitando 6 días
    Then el sistema responde HTTP 400 Bad Request
    And el payload contiene detail: "Insufficient vacation balance"

  Scenario: AC-03 Revisión de solicitud por usuario no manager directo
    Given una solicitud en estado "PENDING" de un empleado con manager_id "M-001"
    When un MANAGER autenticado con ID "M-002" envía PATCH /vacaciones/{id} con estado "APPROVED"
    Then el sistema responde HTTP 403 Forbidden
    And el payload contiene detail: "Unauthorized: Not the direct manager"
```