"""Create requested AGH account over SSH stdin; never persist its plaintext password."""
import base64
import json
import os
import secrets
import sys

import bcrypt
from router_tool import connect

password = os.environ['ADGUARD_TASK_PASSWORD']
username = os.environ.get('ADGUARD_TASK_USERNAME', 'admin')
client = connect()
try:
    if '--verify' in sys.argv:
        # Feed login JSON to curl's stdin; never put the requested password in a file.
        command = """umask 077
trap 'rm -f /tmp/mudi7-account-cookie' EXIT
code=$(curl -sS --max-time 8 -c /tmp/mudi7-account-cookie -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:3000/control/login)
printf 'fresh_user_login=%s\\n' "$code"
[ "$code" = 200 ] || exit 1
code=$(curl -sS --max-time 8 -b /tmp/mudi7-account-cookie -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/control/status)
printf 'fresh_user_protected_api=%s\\n' "$code"
[ "$code" = 200 ] || exit 1
code=$(curl -sS --max-time 8 -b /tmp/mudi7-account-cookie -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/control/profile)
printf 'fresh_user_profile=%s\\n' "$code"
[ "$code" = 200 ] || exit 1
"""
        stdin, stdout, stderr = client.exec_command(command)
        stdin.write(json.dumps({'name': username, 'password': password}))
        stdin.channel.shutdown_write()
        output = stdout.read().decode()
        error = stderr.read().decode()
        if stdout.channel.recv_exit_status():
            raise RuntimeError('fresh account verification failed: ' + error)
        print(output.strip())
        raise SystemExit(0)
    service_password = secrets.token_urlsafe(32)
    data = {
        'name': username,
        'password_hash': bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode(),
        'service_name': 'mudi7-local-api',
        'service_hash': bcrypt.hashpw(service_password.encode(), bcrypt.gensalt(12)).decode(),
        'authorization': 'Basic ' + base64.b64encode(
            ('mudi7-local-api:' + service_password).encode()).decode(),
    }
    # Service is stopped before config writes; the caller handles restart/rollback.
    stdin, stdout, stderr = client.exec_command('umask 077; ruby /tmp/mudi7-adguard-account.rb')
    stdin.write(json.dumps(data))
    stdin.channel.shutdown_write()
    result = stdout.read().decode()
    error = stderr.read().decode()
    status = stdout.channel.recv_exit_status()
    if status:
        raise RuntimeError('account configuration failed: ' + error)
    print(result.strip())
finally:
    client.close()
