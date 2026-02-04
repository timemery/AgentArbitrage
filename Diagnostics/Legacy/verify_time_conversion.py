from datetime import datetime, timezone, timedelta

def _convert_keepa_time_to_iso(keepa_minutes):
    """Converts Keepa time (minutes since 2011-01-01) to ISO 8601 UTC string."""
    keepa_epoch = datetime(2011, 1, 1, tzinfo=timezone.utc)
    dt_object = keepa_epoch + timedelta(minutes=keepa_minutes)
    return dt_object.isoformat()

def _convert_iso_to_keepa_time(iso_str):
    """Converts an ISO 8601 UTC string to Keepa time (minutes since 2011-01-01)."""
    if not iso_str:
        return 0
    dt_object = datetime.fromisoformat(iso_str).astimezone(timezone.utc)
    keepa_epoch = datetime(2011, 1, 1, tzinfo=timezone.utc)
    delta = dt_object - keepa_epoch
    return int(delta.total_seconds() / 60)

def test():
    print("--- Time Conversion Diagnostic ---")

    # Test 1: 7836100 (from logs)
    k_time = 7836100
    iso = _convert_keepa_time_to_iso(k_time)
    print(f"1. Keepa Time {k_time} -> ISO: {iso}")

    # Test 2: 2014-11-24 (from logs)
    iso_2014 = "2014-11-24T17:40:00+00:00"
    k_time_2014 = _convert_iso_to_keepa_time(iso_2014)
    print(f"2. ISO {iso_2014} -> Keepa Time: {k_time_2014}")

    # Test 3: Current Time (2025-11-24 roughly)
    now_iso = "2025-11-24T18:46:12+00:00"
    k_time_now = _convert_iso_to_keepa_time(now_iso)
    print(f"3. ISO {now_iso} -> Keepa Time: {k_time_now}")

    # Verification
    if "2025" in iso:
        print("[PASS] Keepa 7836100 converts to 2025 (Correct Epoch 2011).")
    else:
        print("[FAIL] Keepa 7836100 DOES NOT convert to 2025.")

    if k_time_2014 < 3000000:
         print("[PASS] 2014 ISO converts to ~2M minutes (Correct).")
    else:
         print(f"[FAIL] 2014 ISO converted to {k_time_2014} (Unexpected).")

if __name__ == "__main__":
    test()
