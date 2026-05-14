#!/usr/bin/env bash
set -euo pipefail

FRPC_URL="${FRPC_URL:-https://github.com/fatedier/frp/releases}"
PLATFORM_HOST="${PLATFORM_HOST:-127.0.0.1}"

echo "Checking ssh service"
systemctl enable ssh || true
systemctl restart ssh || true

echo "Checking vnc service"
systemctl enable vncserver || true
systemctl restart vncserver || true

echo "Preparing frpc minimal registration tunnel"
mkdir -p /etc/frp
cat >/etc/frp/frpc.toml <<EOF
serverAddr = "$PLATFORM_HOST"
serverPort = 7000

[[proxies]]
name = "bootstrap-ssh"
type = "tcp"
localIP = "127.0.0.1"
localPort = 22
remotePort = 10000
EOF

echo "frpc configuration written. Download frpc from: $FRPC_URL"
