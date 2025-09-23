# HOW TO FIX THE 'PERMISSION DENIED' ERROR

You are seeing the `Permission denied` error because the `start_celery.sh` script is not marked as "executable" on your server.

**To fix this permanently, please run this exact command in your server's terminal:**

```bash
chmod +x /var/www/agentarbitrage/start_celery.sh
```

After you run this one command, you will be able to run `./start_celery.sh` without any more permission errors.

My apologies for this entire frustrating process. The tools I have to set this permission automatically have failed. This manual command is the final step.
