# De demo a producción

Controles que una empresa añadiría. Ninguno de la tercera columna está implementado.

| Riesgo | Control del demo | Evolución productiva |
|---|---|---|
| Código del repo escapa del contenedor | Docker sin root, sin capabilities, rootfs de solo lectura, sin socket | Aislamiento fuerte: gVisor o microVM, perfil seccomp propio, red por proxy con allowlist de destinos |
| El agente ejecuta comandos peligrosos | No tiene shell | Allowlist de comandos y verificadores expuestos como herramientas, con hook por invocación |
| Prompt injection desde el repo | Sin herramientas con efectos externos; `setting_sources=[]`; hallazgos como datos | Lector aislado de contenido no confiable; juez LLM de alcance; evals de inyección |
| La clave del modelo se filtra | Solo en el contenedor del agente; se bloquea su valor literal en el diff | Proxy que inyecta la credencial; claves efímeras por ejecución |
| Consumo o cambios desmedidos | 25 turnos, 2 sesiones, 600 s por contenedor | Presupuesto por ejecución (`max_budget_usd`), límite de líneas y archivos del diff, alertas |
| Muchos hallazgos y repos | Dos hallazgos sembrados, sin priorizar | Priorización por impacto, riesgo y esfuerzo; orquestación de flota |
| Credencial de publicación amplia | Sesión local de `gh` o token de grano fino | GitHub App con token de instalación de vida corta y permisos mínimos |
| No se puede reconstruir qué pasó | `report.json` por ejecución | Auditoría completa: trazas de cada herramienta, retención y correlación con el PR |
| Ejecuciones repetidas duplican PR | Cada ejecución crea una rama nueva | Idempotencia: una rama y un PR por hallazgo, reanudación tras interrupciones |
| Una versión nueva rompe o está comprometida | Se fija la versión que corrige el advisory | Política de actualización: vulnerabilidades de inmediato; versiones ordinarias tras una ventana de estabilización |
| Dependencia o imagen manipulada | Versiones fijadas con `==` | Hashes en requirements, SBOM, firma y verificación de artefactos |
| El detector pasa sin que el problema esté resuelto | Juez con conteo, pip-audit, un warning, un test nuevo | Más pruebas y políticas: cobertura, mutation testing, SAST, OSV-Scanner/deps.dev, revisión humana obligatoria por riesgo |
| Un cambio validado falla en producción | No hay despliegue | Despliegue gradual, métricas de salud y rollback automático |
