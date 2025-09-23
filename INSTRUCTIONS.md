# HOW TO FIX THE 500 INTERNAL SERVER ERROR

I have found and fixed the cause of the 500 Internal Server Error. The Apache configuration was pointing to the wrong file.

**Please follow these two steps exactly:**

1.  **Pull the latest changes from the git repository.** This will update the `agentarbitrage.conf` file with the fix.

2.  **Restart the Apache server** for the change to take effect. Run this command:
    ```bash
    sudo systemctl restart apache2
    ```

After restarting Apache, the website should load correctly. You can then proceed with testing the Celery worker by running `./start_celery.sh`.
