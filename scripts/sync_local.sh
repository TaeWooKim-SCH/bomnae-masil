#!/usr/bin/env bash
# 클라우드(Supabase) DB → 로컬 오프라인 DB 통째 복사 (#8)
# 실행 시점: 통합2 직후(#40) · 리허설 직후(#45) — 데모 대본에 포함
# 사용법: ./scripts/sync_local.sh
#   SUPABASE_URI 환경변수가 없으면 backend/.env의 DATABASE_URL을 쓴다.
#   pg_dump·pg_restore는 로컬 db 컨테이너(PG17) 안에서 실행 — 클라이언트 버전 불일치 함정 회피.
set -euo pipefail
cd "$(dirname "$0")/.."

SUPABASE_URI="${SUPABASE_URI:-$(grep -E '^DATABASE_URL=' backend/.env 2>/dev/null | head -1 | cut -d= -f2-)}"
if [ -z "$SUPABASE_URI" ]; then
  echo "✗ SUPABASE_URI가 없습니다 — backend/.env의 DATABASE_URL을 확인하세요"; exit 1
fi
case "$SUPABASE_URI" in
  *pooler.supabase.com*) ;;
  *supabase.co*) echo "✗ Direct connection 주소입니다 — Session pooler URI를 쓰세요(#4)"; exit 1 ;;
  *) echo "✗ Session pooler URI가 아닙니다 — backend/.env가 로컬 전환(cp .env.local) 상태일 수 있습니다."
     echo "  클라우드 URI를 SUPABASE_URI 환경변수로 넘기거나 backend/.env를 원복하세요."; exit 1 ;;
esac

echo "1/4 로컬 DB 기동·대기"
docker compose up -d db >/dev/null
docker compose exec -T db sh -c 'until pg_isready -U postgres -q; do sleep 1; done'

echo "2/4 클라우드 덤프 (public 스키마만 — Supabase 내부 스키마는 우리 앱과 무관)"
docker compose exec -T db pg_dump "$SUPABASE_URI" \
  --schema=public --no-owner --no-privileges -Fc -f /tmp/bomnae.dump

echo "3/4 로컬 복원 (spatial_ref_sys 계열 경고는 무시해도 됨 — 아래 4단계 대조가 성공 판정)"
docker compose exec -T db pg_restore --clean --if-exists --no-owner --no-privileges \
  -U postgres -d postgres /tmp/bomnae.dump \
  || echo "  (경고/부분 오류 있음 — 4단계 대조로 판정)"

echo "4/4 테이블·행 수 대조 (spatial_ref_sys 제외)"
# 한계: 행 수 일치는 복원 성공의 휴리스틱이다(내용 일치 보장 아님). 클라우드 행 수는 덤프
# 시점이 아니라 지금 다시 세므로, 라이브 쓰기(리허설 중 세션·인증)와 겹치면 복원이 정상이어도
# 불일치가 날 수 있다 → 그 경우 한 번 더 실행하면 된다.
COMPARE_SQL="select t.tablename || ' ' || (xpath('/row/c/text()', query_to_xml(format('select count(*) c from public.%I', t.tablename), false, true, '')))[1]::text
from pg_tables t where schemaname='public' and tablename <> 'spatial_ref_sys' order by 1"
CLOUD=$(docker compose exec -T db psql "$SUPABASE_URI" -At -c "$COMPARE_SQL")
LOCAL=$(docker compose exec -T db psql -U postgres -At -c "$COMPARE_SQL")
echo "--- 클라우드 ---"; echo "$CLOUD"
echo "--- 로컬 ---"; echo "$LOCAL"
if [ "$CLOUD" = "$LOCAL" ]; then
  echo "✓ 동기화 성공 — 테이블·행 수 일치. 오프라인 기동: docker compose up -d"
else
  echo "✗ 불일치 — 라이브 쓰기와 겹쳤을 수 있습니다. 한 번 더 실행해 보고, 계속 다르면 위 두 목록을 비교하세요"; exit 1
fi
