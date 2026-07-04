#!/bin/bash
# Poranne przygotowanie pokazu JEDNĄ komendą: demo/rano.sh
#   1. budzi Dockera (OrbStack) i Airflow
#   2. cofa hurtownię o dzień (revert paczki DZIEN + pipeline z run_glue=TRUE)
#   3. czeka na zielono i pokazuje stan
#   4. odpala licznik na pełnym ekranie (zostaw na rzutnik; Ctrl+C kończy)
# Dodawanie danych przy prowadzącej robisz już TYLKO w Airflow UI:
#   acled_manual_backfill (pobór z API) -> acled_pipeline (run_glue=FALSE).
set -euo pipefail
cd "$(dirname "$0")/.."
export DZIEN="${DZIEN:-2026-07-04}"

echo ">> Budzę Dockera..."
open -a OrbStack 2>/dev/null || true
until docker info >/dev/null 2>&1; do sleep 2; done
(cd airflow && docker compose up -d)

echo ">> Czekam aż Airflow wstanie..."
until (cd airflow && docker compose exec -T airflow airflow dags list -o plain 2>/dev/null | grep -q acled_pipeline); do sleep 5; done

demo/etl_demo.sh przygotuj

echo ">> Czekam na zakończenie pipeline (~8 min)..."
while :; do
  st=$(cd airflow && docker compose exec -T airflow airflow dags list-runs acled_pipeline -o plain 2>/dev/null \
       | grep '^acled_pipeline' | head -1 | awk '{print $3}')
  case "$st" in
    success) echo ">> Pipeline zielony."; break;;
    failed)  echo ">> Pipeline FAILED — zajrzyj do Airflow UI (hasło niżej):"
             (cd airflow && docker compose exec -T airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated)
             exit 1;;
  esac
  sleep 20
done

demo/etl_demo.sh status
echo
echo ">> Hasło do Airflow UI (admin):"
(cd airflow && docker compose exec -T airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated)
echo
echo ">> Odpalam licznik — zostaw go na ekranie. (Ctrl+C kończy)"
sleep 3
exec python3 demo/pokaz.py
