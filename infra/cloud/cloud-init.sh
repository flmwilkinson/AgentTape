#!/usr/bin/env bash
# Hetzner CX22 bootstrap. Paste into the Cloud Console's "User data"
# field on first boot, OR run as root over ssh after provisioning.
#
# What this does:
#   1. Updates the OS and installs Docker + compose plugin.
#   2. Creates a non-root deploy user with sudo + docker access and
#      installs your SSH key. Locks down SSH (key-only, no password).
#   3. Configures the firewall (ufw) — only 22/80/443 inbound.
#   4. Installs a systemd timer that runs the slow-tier ingestors
#      once a day. Replaces APScheduler's slow tier (which silently
#      lost runs whenever the host slept past the misfire window —
#      a non-issue on a 24/7 cloud host, but the timer is more
#      observable than an in-process scheduler).
#
# After this script runs, follow infra/cloud/README.md to clone the
# repo, populate /opt/agenttape/.env, and bring the stack up.

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
SSH_PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJTicL6RFS4U9pkecQzS072XxI7+4goAJM2KB96o+Un5 f.l.m.wilkinson@gmail.com"

# ---------------------------------------------------------------- packages
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
apt-get install -y \
	ca-certificates curl gnupg ufw fail2ban unattended-upgrades \
	postgresql-client jq

# Docker official repo — distro-aware so this works on both
# Ubuntu (codenames noble/jammy/…) and Debian (bookworm/bullseye/…).
# A hard-coded "linux/debian" repo on an Ubuntu host tries to fetch a
# `noble` package list that doesn't exist on Debian's server,
# apt-get install fails, set -e aborts, and the deploy user never
# gets created — which surfaces as SSH key-auth failure.
. /etc/os-release
DOCKER_DISTRO="${ID:-ubuntu}"   # "ubuntu" or "debian"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL "https://download.docker.com/linux/${DOCKER_DISTRO}/gpg" | \
	gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
	"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
	https://download.docker.com/linux/${DOCKER_DISTRO} \
	${VERSION_CODENAME} stable" \
	| tee /etc/apt/sources.list.d/docker.list >/dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# ---------------------------------------------------------------- deploy user
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
	useradd -m -s /bin/bash -G sudo,docker "$DEPLOY_USER"
fi
mkdir -p /home/$DEPLOY_USER/.ssh
echo "$SSH_PUBKEY" > /home/$DEPLOY_USER/.ssh/authorized_keys
chmod 700 /home/$DEPLOY_USER/.ssh
chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys
chown -R "$DEPLOY_USER:$DEPLOY_USER" /home/$DEPLOY_USER/.ssh
# Sudo without password for docker / systemctl runs
echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/systemctl" \
	> /etc/sudoers.d/$DEPLOY_USER
chmod 0440 /etc/sudoers.d/$DEPLOY_USER

# ---------------------------------------------------------------- ssh hardening
sed -ri \
	-e 's/^#?PasswordAuthentication.*/PasswordAuthentication no/' \
	-e 's/^#?PermitRootLogin.*/PermitRootLogin prohibit-password/' \
	-e 's/^#?PubkeyAuthentication.*/PubkeyAuthentication yes/' \
	/etc/ssh/sshd_config
systemctl restart ssh

# ---------------------------------------------------------------- firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ---------------------------------------------------------------- repo dir
mkdir -p /opt/agenttape
chown -R "$DEPLOY_USER:$DEPLOY_USER" /opt/agenttape

# ---------------------------------------------------------------- slow-tier timer
# Daily at 03:30 UTC. systemd timer is far better than APScheduler's
# interval+misfire model: a missed run triggers on next boot, never
# silently drops.
cat >/etc/systemd/system/agenttape-slow-tier.service <<'UNIT'
[Unit]
Description=AgentTape slow-tier ingestors (one shot)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/agenttape
User=deploy
ExecStart=/usr/bin/docker compose -f infra/cloud/docker-compose.cloud.yml \
	--profile cron run --rm slow-tier
UNIT

cat >/etc/systemd/system/agenttape-slow-tier.timer <<'UNIT'
[Unit]
Description=Run AgentTape slow-tier ingestors daily

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now agenttape-slow-tier.timer

echo
echo "================================================================"
echo "VPS bootstrap complete."
echo
echo "Next steps (see infra/cloud/README.md):"
echo "  1. ssh deploy@<this-host>"
echo "  2. cd /opt/agenttape && git clone https://github.com/flmwilkinson/AgentTape ."
echo "  3. cp infra/cloud/.env.cloud.example .env  &&  chmod 600 .env"
echo "  4. Edit .env — paste your Neon DATABASE_URL + rotated API keys."
echo "  5. docker compose -f infra/cloud/docker-compose.cloud.yml up -d --build"
echo "================================================================"
