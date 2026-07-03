#!/bin/bash
# Demo ETL na obronę: status / revert / restore.
# Zasada bezpieczeństwa: NIC nie kasujemy na twardo — revert przenosi
# przyrost do demo-backup/, restore przywraca. Stan zawsze odwracalny.
#
#   ./etl_demo.sh status    – liczby + najnowsze zdarzenia + znacznik przyrostu
#   ./etl_demo.sh revert    – schowaj przyrost (DZIEN) do backupu + cofnij znacznik
#   ./etl_demo.sh restore   – przywroc przyrost z backupu (fallback-ingest bez API)
#
# Po revert/restore odpal w Airflow DAG acled_pipeline z run_glue=TRUE
# (silver musi sie przebudowac z zmienionego bronze).
set -euo pipefail
export AWS_DEFAULT_REGION=eu-central-1

BRONZE=s3://mw-acled-bronze-dev
BACKUP=$BRONZE/demo-backup
STATE=$BRONZE/state/last_run_timestamp.txt
DZIEN="${DZIEN:-2026-07-02}"          # przyrost do chowania (override: DZIEN=... ./etl_demo.sh revert)
COFNIJ_SEK=$((3*86400))               # o ile cofnac znacznik (3 dni — ingest z API dociagnie z zapasem)

ATHENA_OUT=s3://mw-acled-gold-dev/athena-results/
athena() {
  local qid
  qid=$(aws athena start-query-execution --query-string "$1" \
        --query-execution-context Database=acled_dev \
        --result-configuration OutputLocation=$ATHENA_OUT \
        --work-group primary --query QueryExecutionId --output text)
  while :; do
    local st
    st=$(aws athena get-query-execution --query-execution-id "$qid" \
         --query 'QueryExecution.Status.State' --output text)
    case $st in SUCCEEDED) break;; FAILED|CANCELLED) echo "ATHENA $st"; return 1;; esac
    sleep 1
  done
  aws athena get-query-results --query-execution-id "$qid" \
    --query 'ResultSet.Rows[].Data[].VarCharValue' --output text
}

case "${1:-}" in
status)
  echo "== ZNACZNIK PRZYROSTU (unix ts) =="
  aws s3 cp "$STATE" - 2>/dev/null && echo
  echo "== DNI W BRONZE =="
  aws s3 ls $BRONZE/events/ | sed 's/ *PRE //'
  echo "== BACKUP (schowane przyrosty) =="
  aws s3 ls $BACKUP/events/ 2>/dev/null | sed 's/ *PRE //' || echo "(pusty)"
  echo "== GOLD: liczba zdarzen + najswiezsza data =="
  athena "SELECT count(*), max(event_date) FROM acled_dev.gold_events_wide"
  echo "== 5 NAJNOWSZYCH ZDARZEN =="
  athena "SELECT event_date, country, event_type, fatalities FROM acled_dev.gold_events_wide ORDER BY event_date DESC, event_id_cnty DESC LIMIT 5"
  ;;
revert)
  echo ">> Chowam przyrost $DZIEN do backupu (events + deletes)..."
  aws s3 mv $BRONZE/events/$DZIEN/  $BACKUP/events/$DZIEN/  --recursive --quiet
  aws s3 mv $BRONZE/deletes/$DZIEN/ $BACKUP/deletes/$DZIEN/ --recursive --quiet 2>/dev/null || true
  echo ">> Zapisuje kopie znacznika i cofam go o $((COFNIJ_SEK/86400)) dni..."
  TS=$(aws s3 cp "$STATE" -)
  echo "$TS" | aws s3 cp - "$BACKUP/last_run_timestamp.$DZIEN.txt"
  echo $((TS - COFNIJ_SEK)) | aws s3 cp - "$STATE"
  echo ">> OK. Teraz: Airflow -> acled_pipeline -> Trigger z run_glue=TRUE."
  echo ">>     (silver przebuduje sie bez przyrostu; potem './etl_demo.sh status')"
  ;;
restore)
  echo ">> Przywracam przyrost $DZIEN z backupu (fallback-ingest, bez API)..."
  aws s3 cp $BACKUP/events/$DZIEN/  $BRONZE/events/$DZIEN/  --recursive --quiet
  aws s3 cp $BACKUP/deletes/$DZIEN/ $BRONZE/deletes/$DZIEN/ --recursive --quiet 2>/dev/null || true
  aws s3 cp "$BACKUP/last_run_timestamp.$DZIEN.txt" "$STATE" 2>/dev/null \
    && echo ">> Znacznik przywrocony." || echo ">> (brak kopii znacznika — pomijam)"
  echo ">> OK. Teraz: Airflow -> acled_pipeline -> Trigger z run_glue=TRUE."
  ;;
*)
  grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -12
  ;;
esac
