"""
WSGI Hang Diagnostic Script
Usage: python3 Diagnostics/diagnose_wsgi_hang.py

This script simulates WSGI requests via the Flask test client to identify
where requests are hanging. It executes route calls with a timeout,
captures thread stack traces if a hang occurs, and monitors for unclosed
sqlite3 connections.
"""

import sys
import os
import time
import threading
import traceback
import gc
import sqlite3

# Adjust path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from wsgi_handler import app

def count_sqlite_connections():
    """Returns the number of alive sqlite3.Connection objects."""
    count = 0
    for obj in gc.get_objects():
        if isinstance(obj, sqlite3.Connection):
            count += 1
    return count

def print_thread_stack_traces():
    """Prints the stack traces of all current threads."""
    print("\n--- STACK TRACES OF ALL THREADS ---")
    for thread_id, frame in sys._current_frames().items():
        thread_name = "Unknown"
        for t in threading.enumerate():
            if t.ident == thread_id:
                thread_name = t.name
                break
        print(f"\nThread ID: {thread_id} ({thread_name})")
        traceback.print_stack(frame, file=sys.stdout)
    print("-----------------------------------\n")

def test_route(client, route, timeout=10.0):
    print(f"\nTesting route: {route}")

    conn_count_before = count_sqlite_connections()
    print(f"sqlite3 connections before request: {conn_count_before}")

    result = {
        'route': route,
        'status': 'HUNG',
        'duration': timeout,
        'conn_leak': 0,
        'error': None
    }

    def target():
        try:
            with app.test_request_context(route):
                # We need to simulate the user session if needed, but for now just a GET request
                # actually test_client does GET
                pass

            response = client.get(route)
            result['status'] = f"SUCCESS ({response.status_code})"
        except Exception as e:
            result['status'] = "ERROR"
            result['error'] = str(e)

    start_time = time.time()
    t = threading.Thread(target=target, name=f"RequestThread-{route}")
    t.daemon = True # allow program to exit if thread hangs forever
    t.start()

    t.join(timeout)

    end_time = time.time()
    duration = end_time - start_time
    result['duration'] = duration

    if t.is_alive():
        print(f"Route {route} HUNG! Exceeded timeout of {timeout}s.")
        print_thread_stack_traces()
    else:
        print(f"Route {route} completed in {duration:.2f}s with status: {result['status']}")
        if result['error']:
            print(f"Error details: {result['error']}")

    conn_count_after = count_sqlite_connections()
    print(f"sqlite3 connections after request: {conn_count_after}")

    leak = conn_count_after - conn_count_before
    if leak > 0:
        print(f"WARNING: Possible connection leak detected! {leak} unclosed connections.")
    result['conn_leak'] = leak

    return result

def main():
    print("Starting WSGI Hang Diagnostic...")

    routes_to_test = [
        '/',
        '/dashboard',
        '/api/deals',
        '/api/deals?agents_choice=1'
    ]

    client = app.test_client()

    results = []

    for route in routes_to_test:
        res = test_route(client, route, timeout=15.0)
        results.append(res)
        # slight pause between tests
        time.sleep(1)

    print("\n================ DIAGNOSTIC REPORT ================")
    print(f"{'ROUTE':<30} | {'STATUS':<15} | {'TIME(s)':<8} | {'CONN LEAK'}")
    print("-" * 70)
    for res in results:
        leak_str = str(res['conn_leak']) if res['conn_leak'] > 0 else "0"
        print(f"{res['route']:<30} | {res['status']:<15} | {res['duration']:<8.2f} | {leak_str}")
    print("===================================================\n")

if __name__ == "__main__":
    main()
