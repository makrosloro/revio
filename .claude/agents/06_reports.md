---
name: reports
description: Usar para construir o modificar el sistema de informes semanales en PDF enviados por Telegram. Fase 2 — implementar cuando haya clientes Pro pagando durante al menos 2 semanas.
---

# Agente 06 — Informes Semanales (Fase 2)

## Prerequisito
Agentes 01-05 completados. Al menos 2 semanas de datos de reseñas acumulados en producción.

## Objetivo
Cada lunes a las 9:00 (hora España), los usuarios Pro y Multi reciben por Telegram un PDF con el resumen de reputación de la semana anterior.

## Tareas en orden

### 1. Repositorio de estadísticas (app/repositories/stats_repo.py)
Queries para el período dado (date_from, date_to) filtradas siempre por business_id + user_id:
- `get_rating_average(business_id, user_id, date_from, date_to)` → float
- `get_reviews_by_rating(business_id, user_id, date_from, date_to)` → dict {1: N, 2: N, ...5: N}
- `get_reviews_count(business_id, user_id, date_from, date_to)` → int
- `get_avg_vs_previous_week(business_id, user_id)` → tuple(float_this, float_prev)
- `get_worst_reviews(business_id, user_id, date_from, date_to, limit=3)` → List[Review]

### 2. Generador de PDF (app/services/report_service.py)
Usar `reportlab` (añadir a requirements.txt). Función `generate_weekly_report(user, businesses, week_stats) → bytes`.

Estructura del PDF (A4, márgenes 2cm):
- **Cabecera:** Logo/nombre Revio, período del informe, nombre del negocio
- **Resumen ejecutivo:** media actual, variación vs semana anterior (↑↓), total reseñas nuevas
- **Distribución de ratings:** barra simple en texto (★★★★★ ▓▓▓▓▓░░░░░ 60%)
- **Top 3 peores reseñas:** texto truncado a 150 chars, fecha, plataforma
- **Recomendación:** 1 frase generada según los datos ("Esta semana la principal queja fue el tiempo de espera")
- **Pie:** "Generado por Revio · Próximo informe el lunes"

Si el usuario tiene Plan Multi con varios negocios: un bloque por negocio en el mismo PDF.

No usar imágenes ni fuentes externas — el PDF debe generarse sin conexión a internet.

### 3. Scheduler — job semanal
Añadir job `send_weekly_reports` en APScheduler: `CronTrigger(day_of_week='mon', hour=9, minute=0, timezone='Europe/Madrid')`.

Lógica:
1. Obtener todos los users con `plan in ('pro', 'multi')` y `sub_status = 'active'`
2. Para cada user con `telegram_user_id` no nulo: generar PDF en memoria (no guardar en disco)
3. Enviar con `bot.send_document(chat_id, document=BytesIO(pdf_bytes), filename=f"informe_{fecha}.pdf")`
4. Si falla el envío: log de error, reintento en 1h (solo 1 reintento)

### 4. Comando /informe bajo demanda
Protegido (pro). Genera y envía el informe de los últimos 7 días al instante. Mismo PDF que el automático. Añadir rate limit: máximo 1 vez por día por usuario (guardar timestamp en BD).

### 5. Comando /stats (versión texto para free)
Protegido (free). Versión mínima en texto plano: media actual, número de reseñas nuevas esta semana. Sin PDF, sin desglose. Es el incentivo para hacer upgrade a Pro.

## Datos mínimos para que el informe sea útil
El informe solo se envía si el negocio tiene al menos 3 reseñas en el período. Si no: enviar mensaje de texto indicando que aún hay pocos datos y cuándo se enviará el primero.

## Verificación
```bash
# Generar PDF de prueba con datos sintéticos
python -c "
from app.services.report_service import generate_weekly_report
from datetime import date
pdf_bytes = generate_weekly_report(
    business_name='Restaurante Test',
    period='24-30 Nov 2025',
    avg_rating=3.8,
    prev_avg=4.1,
    total_reviews=12,
    distribution={1:2, 2:1, 3:3, 4:4, 5:2},
    worst_reviews=[
        {'text': 'Tardaron 45 minutos en servirnos', 'rating': 2, 'date': '28 Nov'},
    ]
)
open('/tmp/test_report.pdf', 'wb').write(pdf_bytes)
print(f'PDF generado: {len(pdf_bytes)} bytes')
"
# Abrir /tmp/test_report.pdf y verificar visualmente
```
