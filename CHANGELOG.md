# Changelog — NegocioSano

Todos los cambios notables del proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionado según [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Added
### Changed
### Fixed
### Removed

---

## [0.1.0] — YYYY-MM-DD

### Added
- Estructura inicial del proyecto (FastAPI + PostgreSQL + python-telegram-bot)
- Sistema de autenticación multi-tenant via Stripe + token de activación
- Polling de reseñas de Google Maps cada 2 horas con clasificación por sentimiento
- Alertas inmediatas para reseñas negativas (≤3★) con borrador de respuesta IA
- Resumen diario a las 21:00 para reseñas positivas (≥4★) con borradores de respuesta
- Dos prompts de IA diferenciados: negativas (desactivar queja) y positivas (reforzar relación)
- Middleware `require_subscription` para control de acceso por plan (Free/Pro/Multi)
- Comandos: /start, /activar, /suscribir, /config, /agregar, /pausa, /reanudar, /estado, /resenas, /responder
- Webhook de Stripe: alta, cancelación, pago fallido
- Publicación directa en Google vía Google Business Profile API con botones inline en Telegram (plan Multi)
- GitFlow configurado con ramas main/develop
- CI/CD con GitHub Actions y runner self-hosted en NAS Synology
- Docker Compose para NAS con Cloudflare Tunnel
- Backup automático diario de PostgreSQL
- Documentación completa en docs/ (arquitectura, despliegues, migración)

---

<!-- 
Guía de versiones:
  PATCH (0.1.X): fix de bug, ajuste menor
  MINOR (0.X.0): nueva funcionalidad (nuevo comando, nueva plataforma)
  MAJOR (X.0.0): cambio que rompe compatibilidad

Tipos de cambio:
  Added      nueva funcionalidad
  Changed    cambio en funcionalidad existente
  Fixed      corrección de bug
  Removed    funcionalidad eliminada
  Security   corrección de vulnerabilidad
-->
