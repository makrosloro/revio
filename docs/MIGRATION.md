# Migración NAS → Servidor Dedicado

> Ejecutar esta guía cuando el MRR supere los 1.000€/mes o cuando el NAS tenga problemas de estabilidad recurrentes.
> Tiempo estimado de la migración: 2-4 horas. Downtime esperado: 10-20 minutos.

## Checklist de preparación (días antes)

- [ ] Servidor contratado y accesible por SSH
- [ ] Dominio apuntando al servidor (DNS propagado, verificar con `dig TU_DOMINIO.com`)
- [ ] `DEPLOYMENT_SERVER.md` completado: Caddy instalado, usuario deploy creado, SSH keys configuradas
- [ ] Secrets de GitHub actualizados con datos del servidor
- [ ] `.github/workflows/deploy.yml` probado en rama de prueba
- [ ] Backup manual del NAS realizado y verificado (restaurar el dump en una BD local para confirmar que es válido)
- [ ] Comunicar a los clientes: "Mantenimiento programado el [fecha] entre [hora] y [hora]"

---

## Paso 1 — Backup de la BD del NAS

```bash
# En el NAS
ssh TU_USUARIO@192.168.1.155
cd /volume1/docker/revio

# Dump completo con timestamp
docker-compose -f docker-compose.nas.yml exec db \
  pg_dump -U postgres revio > /volume1/backups/pre_migration_$(date +%Y%m%d_%H%M%S).sql

# Verificar que el dump es válido y no está vacío
wc -l /volume1/backups/pre_migration_*.sql
# Debe tener miles de líneas si hay datos

# Copiar el dump a tu máquina local
scp TU_USUARIO@192.168.1.155:/volume1/backups/pre_migration_*.sql ./
```

## Paso 2 — Preparar el servidor

```bash
# Verificar que el servidor está listo
ssh deploy@IP_SERVIDOR "docker --version && docker-compose version"

# Subir el .env al servidor (NUNCA por git)
scp .env deploy@IP_SERVIDOR:/home/deploy/revio/.env

# Subir el docker-compose del servidor
scp docker-compose.server.yml deploy@IP_SERVIDOR:/home/deploy/revio/

# Verificar en el servidor
ssh deploy@IP_SERVIDOR "ls -la /home/deploy/revio/"
```

## Paso 3 — Arrancar la BD en el servidor

```bash
ssh deploy@IP_SERVIDOR
cd /home/deploy/revio

# Solo la BD primero
docker-compose -f docker-compose.server.yml up -d db

# Esperar healthcheck
sleep 20
docker-compose -f docker-compose.server.yml ps
# db debe mostrar "healthy"
```

## Paso 4 — Restaurar el dump en el servidor

```bash
# Desde tu máquina local, copiar el dump al servidor
scp pre_migration_*.sql deploy@IP_SERVIDOR:/home/deploy/revio/

# En el servidor: restaurar
ssh deploy@IP_SERVIDOR
cd /home/deploy/revio
cat pre_migration_*.sql | docker exec -i revio-db-1 psql -U postgres revio

# Verificar restauración
docker exec -it revio-db-1 psql -U postgres -d revio -c "\dt"
docker exec -it revio-db-1 psql -U postgres -d revio -c "SELECT COUNT(*) FROM users;"
docker exec -it revio-db-1 psql -U postgres -d revio -c "SELECT COUNT(*) FROM businesses;"
docker exec -it revio-db-1 psql -U postgres -d revio -c "SELECT COUNT(*) FROM reviews;"
# Comparar counts con los del NAS — deben coincidir exactamente
```

## Paso 5 — INICIO DEL DOWNTIME

```bash
# En el NAS: parar la app (BD sigue corriendo para referencia)
ssh TU_USUARIO@192.168.1.155
docker-compose -f docker-compose.nas.yml stop app tunnel
echo "App parada en NAS — $(date)"
```

## Paso 6 — Segundo dump final (captura los últimos cambios)

```bash
# En el NAS (mientras la app está parada — sin escrituras nuevas)
docker-compose -f docker-compose.nas.yml exec db \
  pg_dump -U postgres revio > /volume1/backups/final_migration_$(date +%Y%m%d_%H%M%S).sql

# Copiar y restaurar en el servidor (igual que pasos anteriores)
scp TU_USUARIO@192.168.1.155:/volume1/backups/final_migration_*.sql ./
scp final_migration_*.sql deploy@IP_SERVIDOR:/home/deploy/revio/
ssh deploy@IP_SERVIDOR "cat /home/deploy/revio/final_migration_*.sql \
  | docker exec -i revio-db-1 psql -U postgres revio"
```

## Paso 7 — Arrancar la app en el servidor

```bash
ssh deploy@IP_SERVIDOR
cd /home/deploy/revio

# Pull de la imagen más reciente (debe existir en GHCR tras el último deploy)
docker-compose -f docker-compose.server.yml pull app

# Arrancar todo
docker-compose -f docker-compose.server.yml up -d

# Ejecutar migraciones pendientes (si las hay)
docker-compose -f docker-compose.server.yml exec app alembic upgrade head

# Verificar logs
docker-compose -f docker-compose.server.yml logs app --tail=50
```

## Paso 8 — Verificación

```bash
# Health check de la app
curl https://TU_DOMINIO.com/health
# → {"status": "ok", "db": "connected"}

# Verificar que el bot de Telegram responde (mandar /start manualmente)

# Verificar que el webhook de Telegram apunta al nuevo servidor
# El WEBHOOK_URL en .env debe ser https://TU_DOMINIO.com

# Verificar que Stripe apunta al nuevo servidor
# Panel Stripe → Webhooks → actualizar URL del endpoint
```

## Paso 9 — FIN DEL DOWNTIME

```bash
# Actualizar webhook de Stripe al nuevo dominio
# Panel Stripe → Developers → Webhooks → Edit endpoint URL
# https://TU_DOMINIO.com/webhook/stripe

# El bot ya está operativo — enviar mensaje al canal de clientes:
# "El mantenimiento ha finalizado. Todo vuelve a funcionar con normalidad."
```

## Paso 10 — Apagado definitivo del NAS (esperar 1 semana)

```bash
# Después de 1 semana de estabilidad en el servidor, apagar el NAS
ssh TU_USUARIO@192.168.1.155
docker-compose -f docker-compose.nas.yml down
# El volumen de PostgreSQL queda en el NAS como backup de emergencia

# Actualizar CLAUDE.md: cambiar "Fase actual: NAS" → "Fase actual: servidor dedicado"
# Actualizar .github/workflows/deploy.yml: eliminar o comentar el job de deploy al NAS
```

---

## Rollback de emergencia a NAS

Si algo sale mal en el servidor durante la migración:

```bash
# Arrancar el NAS de nuevo (la BD no se tocó)
ssh TU_USUARIO@192.168.1.155
docker-compose -f docker-compose.nas.yml up -d

# Verificar que el bot responde en NAS
# El WEBHOOK_URL debe seguir apuntando al tunnel de Cloudflare del NAS
# (si se cambió, revertir en .env del NAS y reiniciar)
```
