#!/bin/sh
# build.sh — compile and sign memhelper with the debugger entitlement.
# No sudo required; ad-hoc signing with the entitlement plist is sufficient
# on macOS 13+ for task_for_pid against your own processes.
set -e
cd "$(dirname "$0")"

echo "==> Compiling memhelper.c …"
cc -O2 -Wall -o memhelper memhelper.c

echo "==> Signing with debugger entitlement …"
codesign --force --sign - --entitlements debugger.entitlements --options runtime memhelper

echo "==> Verifying entitlements …"
codesign -d --entitlements - memhelper

echo "==> Done."
