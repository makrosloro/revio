# Reglas GitFlow — NegocioSano

Claude Code DEBE seguir estas reglas en toda operación que implique git.

## Ramas

| Rama | Propósito | Se crea desde | Se fusiona en |
|---|---|---|---|
| `main` | Producción estable | — | — |
| `develop` | Integración continua | `main` | — |
| `feature/xxx` | Nueva funcionalidad | `develop` | `develop` |
| `release/x.x.x` | Preparación de release | `develop` | `main` + `develop` |
| `hotfix/xxx` | Fix urgente en producción | `main` | `main` + `develop` |

## Nombres de rama
- Features: `feature/nombre-en-kebab-case` (ej: `feature/google-places-polling`)
- Releases: `release/1.0.0` (semver estricto)
- Hotfixes: `hotfix/descripcion-breve` (ej: `hotfix/stripe-webhook-signature`)

## Flujo de trabajo con agentes
Antes de ejecutar cualquier agente, Claude Code DEBE:
1. Verificar en qué rama está: `git branch --show-current`
2. Si está en `main` o `develop`, crear feature branch antes de escribir código
3. Hacer commits atómicos durante la ejecución del agente (no un solo commit masivo al final)

Ejemplo de flujo para el Agente 01:
```bash
git checkout develop
git checkout -b feature/infrastructure-base
# ... Claude Code implementa el agente ...
git add app/database.py
git commit -m "chore: add async PostgreSQL engine and session factory"
git add app/models/
git commit -m "feat: add User, Business, Review and AlertLog models"
git add alembic/
git commit -m "chore: add initial Alembic migration with 4 tables"
git add docker-compose.yml Dockerfile
git commit -m "chore: add Docker Compose with db and app services"
# Al terminar el agente:
git checkout develop
git merge --no-ff feature/infrastructure-base -m "feat: complete infrastructure base (Agent 01)"
git branch -d feature/infrastructure-base
git push origin develop
```

## Formato de commits (Conventional Commits)
```
<tipo>(<scope opcional>): <descripción en minúsculas, imperativo>

Ejemplos:
feat(bot): add /activar command with token validation
fix(scheduler): prevent duplicate review alerts on restart
chore(docker): add healthcheck to db service
refactor(repos): extract user_id filter into base repository
docs: update CHANGELOG with v0.2.0 changes
test(google): add unit tests for Places API client
```

Tipos permitidos: `feat` `fix` `chore` `refactor` `docs` `test` `perf` `ci`

## CHANGELOG.md — obligatorio
Después de cada agente completado o feature mergeada a develop:
1. Abrir `CHANGELOG.md`
2. Añadir entradas en `[Unreleased]` con el formato Keep a Changelog
3. Hacer commit: `docs: update CHANGELOG`

Cuando se crea una release:
1. Mover `[Unreleased]` a `[x.x.x] - YYYY-MM-DD`
2. Añadir nueva sección `[Unreleased]` vacía

## Pull Requests
Aunque es un proyecto solo, abrir PRs de feature → develop para que quede registro documentado de cada cambio. El título del PR sigue el mismo formato que los commits.

## Prohibido
- Commits directos a `main` (solo merges de `release/*` y `hotfix/*`)
- Commits directos a `develop` (solo merges de `feature/*` y `hotfix/*`)
- `git push --force` en `main` o `develop`
- Commits con mensaje genérico: "fix", "update", "changes", "wip"
