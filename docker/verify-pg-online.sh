#!/usr/bin/env bash
# ============================================================
# 部署后自检：pgvector 是否存活、genzltd 数据是否完整
#   —— 与 deploy.yml 的 D1b+ 守卫同口径，供人工在 prod 复核用。
#
# 背景：deploy.yml 会先 `compose down -p looma-zervi --remove-orphans`，
#       它会把项目内所有容器（含 looma-pgvector）删掉，随后靠
#       `up -d --no-build chromadb pgvector` 拉回；数据在 named volume
#       looma-zervi_pgdata 里，容器重建无损。详见
#       docs/PROD_PG_REBUILD_PLAN.md §5.3。
#
# 用法（在 prod 的仓库根目录）：
#   bash docker/verify-pg-online.sh
# 可用环境变量覆盖下限：
#   MIN_TABLES=55 MIN_POEMS=58059 bash docker/verify-pg-online.sh
# ============================================================
set -euo pipefail

CONTAINER=${CONTAINER:-looma-pgvector}
DB_USER=${DB_USER:-looma}
DB_NAME=${DB_NAME:-genzltd}
VOLUME=${VOLUME:-looma-zervi_pgdata}
MIN_TABLES=${MIN_TABLES:-55}
MIN_POEMS=${MIN_POEMS:-58059}
READY_TIMEOUT=${READY_TIMEOUT:-20}

echo "== 1) 容器状态 =="
docker inspect "${CONTAINER}" \
  --format 'id={{.Id}} state={{.State.Status}} health={{.State.Health.Status}} started={{.State.StartedAt}}'

echo "== 2) 就绪探测（<=${READY_TIMEOUT}s）=="
ready=0
for i in $(seq 1 "${READY_TIMEOUT}"); do
  if docker exec "${CONTAINER}" pg_isready -U "${DB_USER}" -d "${DB_NAME}" >/dev/null 2>&1; then
    echo "pgvector ready after ${i}s"
    ready=1
    break
  fi
  sleep 1
done
if [ "${ready}" -ne 1 ]; then
  echo "FAIL: pg_isready 超时 ${READY_TIMEOUT}s" >&2
  exit 1
fi

echo "== 3) 数据口径 =="
IFS='|' read -r TABLES VIEWS ROWS POEMS <<<"$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -tA -c "
select (select count(*) from pg_tables where schemaname='public'),
       (select count(*) from pg_views  where schemaname='public'),
       (select coalesce(sum(n_live_tup), 0) from pg_stat_user_tables),
       (select count(*) from poems)")"
echo "tables=${TABLES} (>=${MIN_TABLES}) views=${VIEWS} rows=${ROWS} poems=${POEMS} (>=${MIN_POEMS})"

if [ "${TABLES}" -lt "${MIN_TABLES}" ]; then
  echo "FAIL: tables=${TABLES} < ${MIN_TABLES} —— 迁移数据可能未随容器复活" >&2
  exit 1
fi
if [ "${POEMS}" -lt "${MIN_POEMS}" ]; then
  echo "FAIL: poems=${POEMS} < ${MIN_POEMS} —— 业务表数据缺失" >&2
  exit 1
fi

echo "== 4) 数据卷（数据面不在容器里，重建无损）=="
docker volume inspect "${VOLUME}" --format 'volume={{.Name}} created={{.CreatedAt}} mountpoint={{.Mountpoint}}'

echo "OK: pgvector online & ${DB_NAME} intact"
