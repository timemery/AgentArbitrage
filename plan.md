1. **Fix CSS Layout for CSV Actions Container**
   - Update `static/global.css` using `replace_with_git_merge_diff` to add `white-space: nowrap;` and `width: max-content;` to the `.csv-actions-container` class to prevent the text from wrapping inside the buttons.
   - Verify changes with `tail -n 25 static/global.css`.

2. **Remove Dead Code**
   - Update `templates/dashboard.html` using `replace_with_git_merge_diff` to remove the dead `renderPagination` function that was left behind.
   - Verify changes using `cat templates/dashboard.html | grep -C 10 renderPagination`.

3. **Re-verify**
   - Start the server `gunicorn --bind 0.0.0.0:8000 wsgi_handler:app &`.
   - Wait 5 seconds.
   - Run the Playwright verification script `python /home/jules/verification/verify_tracking.py` to ensure the UI issue is resolved.
   - Kill the server.

4. **Complete Pre Commit Steps**
   - Request code review again.
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.

5. **Submit**
   - Submit the branch `ui-tracking-pagination-demote-csv` with a descriptive message.
