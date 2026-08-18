"""Unit checks for the tiered SSH permission classifier.

Plain-script (no pytest dependency). Run from project root:
    .venv/bin/python antre/tests/test_permissions.py
"""

import sys

sys.path.insert(0, ".")

from antre.permissions import DangerLevel as D, ssh_command_danger

# command -> expected danger
CASES = {
    # read-only / reporting → SAFE
    "ls -la /var/log": D.SAFE,
    "uptime": D.SAFE,
    "cat /etc/os-release": D.SAFE,
    "git status --short": D.SAFE,
    "git log --oneline -5": D.SAFE,
    "systemctl status nginx": D.SAFE,
    "docker ps -a": D.SAFE,
    "df -h": D.SAFE,
    "sudo ls /root": D.SAFE,
    # routine mutating → MEDIUM (auto-runs in auto mode)
    "apt install nginx": D.MEDIUM,
    "mkdir -p /tmp/x": D.MEDIUM,
    "touch /tmp/flag": D.MEDIUM,
    "systemctl restart nginx": D.MEDIUM,
    "git pull": D.MEDIUM,
    "echo hello": D.SAFE,
    # destructive → CRITICAL (level 5 — the only tier that asks in auto mode)
    "rm -rf /tmp/x": D.CRITICAL,
    "rm foo.txt": D.CRITICAL,
    "sudo shutdown now": D.CRITICAL,
    "reboot": D.CRITICAL,
    "kill -9 1234": D.CRITICAL,
    "pkill nginx": D.CRITICAL,
    "apt purge docker": D.CRITICAL,
    "apt-get remove vim": D.CRITICAL,
    "pip uninstall requests": D.CRITICAL,
    "git reset --hard HEAD": D.CRITICAL,
    "git clean -fd": D.CRITICAL,
    "git push --force origin main": D.CRITICAL,
    "docker stop web": D.CRITICAL,
    "systemctl stop nginx": D.CRITICAL,
    "chmod 000 /etc/shadow": D.CRITICAL,
    "mv /home/ubuntu/data /dev/null": D.CRITICAL,
    # compound commands — each segment is checked
    "ls; rm -rf /tmp/x": D.CRITICAL,
    "cd /tmp && rm -f x": D.CRITICAL,
    "git pull || shutdown": D.CRITICAL,
    "ls -la | grep tmp": D.SAFE,
    # sneaky deletion paths
    "find / -name '*.tmp' -delete": D.CRITICAL,
    "find /var -name x -exec rm {} \\;": D.CRITICAL,
    "find /var -name x | xargs rm": D.CRITICAL,
    "": D.CRITICAL,
}

failed = 0
for cmd, want in CASES.items():
    got = ssh_command_danger(cmd)
    ok = got == want
    failed += 0 if ok else 1
    print(f"{'OK  ' if ok else 'FAIL'} {cmd!r:55} -> {got.name:8} (want {want.name})")

print("-" * 70)
if failed:
    print(f"{failed} FAILED")
    sys.exit(1)
print(f"ALL {len(CASES)} PASSED")
