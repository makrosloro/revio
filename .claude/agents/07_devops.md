---
name: devops
description: Usar para configurar o modificar toda la infraestructura de CI/CD, GitFlow, Docker Compose (NAS y servidor), Makefile y documentación de despliegue. Ejecutar este agente PRIMERO si el repositorio es nuevo.
---

# Agente 07 — DevOps, CI/CD y GitFlow

## Prerequisito
Repositorio privado creado en GitHub. Acceso SSH al NAS configurado. Git instalado en la máquina de desarrollo.

## Objetivo
Dejar el proyecto completamente operativo en GitHub con GitFlow, CI/CD funcional y despliegue automático al NAS. Este agente se ejecuta antes de los demás para sentar la base de trabajo.

## Tareas en orden

### 1. Archivos Docker Compose
Implementar en la raíz del proyecto los tres compose files documentados:
- `docker-compose.yml` — desarrollo local (solo PostgreSQL)
- `docker-compose.nas.yml` — producción NAS: db + app + cloudflare tunnel (ver docs/DEPLOYMENT_NAS.md)
- `docker-compose.server.yml` — futuro servidor: db + redis + app + worker (ver docs/DEPLOYMENT_SERVER.md)

### 2. Dockerfile multistage
Stage `deps`: instalar dependencias desde requirements.txt. Stage `runtime`: copiar código, crear usuario no-root `appuser`, healthcheck con curl al /health, exponer 8000. Usar Python 3.11-slim en ambos stages.

### 3. Archivos de configuración
- `.gitignore`: incluir .env, __pycache__, *.pyc, .pytest_cache, htmlcov, logs/, backups/, *.sql.gz, .DS_Store
- `pyproject.toml`: configurar ruff (E,W,F,I,UP), mypy (ignore_missing_imports=true), pytest (asyncio_mode=auto, testpaths=["tests"])

### 4. Inicializar GitFlow
```bash
git flow init -d
git push -u origin main
git push -u origin develop
```
Verificar en GitHub que ambas ramas existen y develop es la rama por defecto para PRs.

### 5. GitHub Secrets
Configurar en GitHub → Settings → Secrets → Actions:
- `TELEGRAM_BOT_TOKEN`, `BOT_ADMIN_CHAT_ID` (para notificaciones de deploy)
- Los secrets de BD, Stripe y Google se configuran directamente en el .env del NAS, NO en GitHub

### 6. Instalar runner self-hosted en el NAS
Seguir docs/DEPLOYMENT_NAS.md paso 5. Verificar que aparece en GitHub → Settings → Actions → Runners con estado "Idle".

### 7. Primer deploy al NAS
Seguir docs/DEPLOYMENT_NAS.md pasos 1-4. Verificación:
```bash
# Desde el NAS
curl http://localhost:8000/health
# → {"status": "ok", "db": "connected"}
docker-compose -f docker-compose.nas.yml ps
# → app, db y tunnel en estado Up
```

### 8. Protección de ramas en GitHub
Settings → Branches → Add rule:
- `main`: require status checks (CI job), no direct push
- `develop`: require status checks (CI job), no direct push

### 9. Verificar flujo completo
```bash
make feature f=test-setup
echo "# test" >> README.md
git add . && git commit -m "chore: verificar flujo completo"
git flow feature finish test-setup
git push origin develop
# Abrir PR → verificar que CI pasa → merge → verificar deploy en NAS
```

## Documentos de referencia
- `GITFLOW.md` — referencia completa de comandos y flujos
- `Makefile` — todos los comandos con `make help`
- `docs/DEPLOYMENT_NAS.md` — setup completo del NAS
- `docs/DEPLOYMENT_SERVER.md` — setup futuro del servidor
- `docs/MIGRATION.md` — cuando toque migrar de NAS a servidor

## Verificación final
```bash
make test && make lint     # en local: todo verde
# En GitHub Actions: CI pasa en develop, Deploy se ejecuta en runner NAS al hacer push a main
```
