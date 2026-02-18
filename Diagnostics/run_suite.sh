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
echo "=== 4. Pause Status ==="
python3 Diagnostics/check_pause_status.py
echo ""
echo "=== 5. Worker Log Tail ==="
tail -n 20 celery_worker.log

echo ""
echo "=== 6. Deep Dive Recommendation ==="
echo "If rejection rates are high or specific ASINs are missing, run:"
echo "python3 Diagnostics/analyze_rejection_reasons.py"
echo "(This fetches live data to debug logic failures)"
