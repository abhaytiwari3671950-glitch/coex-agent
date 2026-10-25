"""Vercel release checks. Runtime secrets/database must be configured first."""
import os
import subprocess
import sys

subprocess.run([sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'ERROR'], check=True)
# Enable only for the release whose database is being migrated. Preview and
# production should have separate DATABASE_URL values.
if os.environ.get('COEX_RUN_MIGRATIONS') == '1':
    subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
# The Django builder runs collectstatic and serves assets from the Vercel CDN.
