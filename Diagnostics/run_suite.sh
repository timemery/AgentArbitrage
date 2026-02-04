#!/bin/bash
echo "=== 1. System Health Check ==="
python3 Diagnostics/system_health_report.py
echo ""
echo "=== 2. Deal Statistics ==="
python3 Diagnostics/comprehensive_diag.py
echo ""
echo "=== 3. Pipeline Flow ==="
python3 Diagnostics/diagnose_dwindling_deals.py
echo ""
echo "=== 4. Worker Log Tail ==="
tail -n 20 celery_worker.log
