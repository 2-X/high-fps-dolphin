#!/bin/bash
# Launch the real BSMSO dedicated server natively on macOS.
# Prints "Server listening on TCP+UDP port 27015" when ready.
set -e
export DOTNET_ROOT=/usr/local/Cellar/dotnet/10.0.101/libexec
cd "$(dirname "$0")/../bundle-server"
exec "$DOTNET_ROOT/dotnet" SMSO.ServerHost.dll "$@"
