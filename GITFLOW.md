# GitFlow — Revio

Referencia completa del flujo de trabajo. Todos los comandos son los mismos en NAS y en servidor futuro — solo cambia el destino del despliegue.

## Estructura de ramas

```
main          → producción (lo que está desplegado y funcionando)
develop       → integración (acumula features terminadas)
feature/xxx   → nueva funcionalidad (sale de develop, vuelve a develop)
release/x.x.x → preparación de release (sale de develop, va a main + develop)
hotfix/xxx    → fix urgente en producción (sale de main, va a main + develop)
```

## Configuración inicial (una sola vez por máquina)

```bash
# Instalar git-flow
brew install git-flow-avh          # macOS
sudo apt install git-flow          # Ubuntu/Debian

# Clonar el repositorio
git clone git@github.com:TU_USUARIO/revio.git
cd revio

# Inicializar GitFlow con los valores por defecto
git flow init -d
# Acepta todos los defaults:
# Production branch: main
# Development branch: develop
# Feature prefix: feature/
# Release prefix: release/
# Hotfix prefix: hotfix/
# Version tag prefix: v

# Verificar la configuración
cat .git/config | grep -A 10 "gitflow"
```

## Flujo diario — Features

Una feature es cualquier nueva funcionalidad: un nuevo comando del bot, una integración nueva, una mejora de UI.

```bash
# 1. Empezar feature (siempre desde develop actualizado)
git checkout develop && git pull origin develop
git flow feature start nombre-descriptivo-en-kebab-case

# Ejemplos de nombres correctos:
# git flow feature start google-places-polling
# git flow feature start stripe-webhook-handler
# git flow feature start tripadvisor-scraper

# 2. Trabajar en la feature — commits frecuentes y descriptivos
git add -p                                    # añadir cambios por hunks, no todo de golpe
git commit -m "feat: implementar polling de Google Places API"
git commit -m "test: añadir tests unitarios para GooglePlacesClient"
git commit -m "docs: documentar variables de entorno de Google API"

# 3. Mantener la feature actualizada si develop avanza
git fetch origin
git rebase origin/develop                    # preferir rebase sobre merge en features

# 4. Terminar la feature (merge a develop, borra la rama local)
git flow feature finish nombre-descriptivo-en-kebab-case

# 5. Subir develop actualizado
git push origin develop
```

## Flujo de releases

Una release agrupa varias features terminadas en develop y las prepara para producción.

```bash
# 1. Verificar que develop está limpio y los tests pasan
git checkout develop && git pull origin develop
make test                                    # debe pasar al 100%

# 2. Decidir el número de versión (Semantic Versioning)
# MAJOR: cambio incompatible (muy raro en fase inicial)
# MINOR: nueva feature que no rompe nada (lo más habitual)
# PATCH: solo fixes y ajustes menores

# 3. Iniciar la release
git flow release start 1.2.0                # crea rama release/1.2.0 desde develop

# 4. Preparar la release — SOLO estos cambios permitidos:
# - Actualizar CHANGELOG.md con los cambios de esta versión
# - Bump de versión en pyproject.toml o __version__
# - Fixes de último momento (nunca features nuevas)
# - Actualizar docs si algo cambió

nano CHANGELOG.md                           # documentar todos los cambios
git add CHANGELOG.md
git commit -m "chore: preparar release v1.2.0"

# 5. Terminar la release
# Esto hace: merge a main + tag v1.2.0 + merge de vuelta a develop + borra la rama
git flow release finish 1.2.0
# El editor abrirá para el mensaje del tag — escribir resumen de la release

# 6. Subir todo
git push origin main
git push origin develop
git push origin --tags                      # esto dispara el deploy automático al NAS
```

## Flujo de hotfixes

Un hotfix corrige un bug crítico en producción sin pasar por el ciclo normal de develop.

```bash
# Escenario: hay un bug en producción (main) que rompe algo para los clientes

# 1. Iniciar hotfix desde main
git checkout main && git pull origin main
git flow hotfix start fix-descripcion-breve

# Ejemplos:
# git flow hotfix start stripe-webhook-signature-error
# git flow hotfix start bot-crash-on-empty-review

# 2. Hacer solo el fix mínimo necesario — no aprovechar para más cosas
git add -p
git commit -m "fix: corregir verificación de firma en webhook de Stripe"
git commit -m "test: añadir test para el caso de firma inválida"

# 3. Actualizar CHANGELOG.md
nano CHANGELOG.md
git commit -m "docs: actualizar CHANGELOG con hotfix v1.2.1"

# 4. Terminar el hotfix
# Hace: bump de PATCH version + merge a main + tag + merge a develop + borra rama
git flow hotfix finish fix-descripcion-breve

# 5. Subir
git push origin main
git push origin develop
git push origin --tags                      # dispara deploy de emergencia
```

## Convención de commits (Conventional Commits)

```
<tipo>(<scope opcional>): <descripción en imperativo>

feat:     nueva funcionalidad
fix:      corrección de bug
docs:     solo documentación
style:    formato, espacios (sin cambio de lógica)
refactor: refactorización sin cambio de comportamiento
test:     añadir o modificar tests
chore:    tareas de mantenimiento (deps, config, CI)
perf:     mejora de rendimiento

Ejemplos correctos:
feat(bot): añadir comando /regenerar para borradores de IA
fix(scheduler): corregir race condition en polling paralelo
docs(deployment): actualizar guía de NAS con nuevo puerto
chore(deps): actualizar python-telegram-bot a 20.7
test(auth): añadir tests para middleware de suscripción
```

## Pull Requests

Todo trabajo va en PR a `develop` (nunca push directo a `develop` o `main`).

```bash
# Tras terminar una feature y hacer push
git push origin feature/nombre-feature

# Abrir PR en GitHub:
# Base: develop
# Compare: feature/nombre-feature
# Usar el template de .github/pull_request_template.md
# Asignar a ti mismo
# Añadir label: feature / fix / docs / chore
```

## Alias útiles de git

Añadir a `~/.gitconfig`:

```ini
[alias]
    lg = log --oneline --graph --decorate --all
    st = status -sb
    unstage = reset HEAD --
    last = log -1 HEAD --stat
    aliases = config --get-regexp alias
```

## Referencia rápida de comandos

| Acción | Comando |
|--------|---------|
| Nueva feature | `git flow feature start nombre` |
| Terminar feature | `git flow feature finish nombre` |
| Nueva release | `git flow release start X.Y.Z` |
| Terminar release | `git flow release finish X.Y.Z` |
| Nuevo hotfix | `git flow hotfix start nombre` |
| Terminar hotfix | `git flow hotfix finish nombre` |
| Ver estado | `git flow feature list` / `git flow release list` |
| Subir tags | `git push origin --tags` |
