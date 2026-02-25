# AgriBooks — Production Deployment Guide
## Hostinger VPS + Custom Domain + Cloudflare R2

---

## Overview

```
Internet → Your Domain (DNS A record → VPS IP)
         → Nginx (port 80/443, SSL)
              ├── / → React build (static files)
              └── /api → FastAPI (port 8001, Supervisor)
                          └── MongoDB (local, port 27017)
                          └── Backups → Cloudflare R2
```

---

## PHASE 1 — Save Code to GitHub

Before leaving Emergent, push your code to GitHub.

1. In the Emergent chat input, click **"Save to Github"**
2. Connect your GitHub account and create a repo (e.g. `agribooks`)
3. Note your repo URL: `https://github.com/YOUR_USERNAME/agribooks`

---

## PHASE 2 — Cloudflare R2 Setup (do this first, get credentials ready)

1. Go to **dash.cloudflare.com** → R2 Object Storage
2. Click **Create bucket** → name it `agribooks-files`
3. Create a second bucket → name it `agribooks-backups`
4. Go to **R2 → Manage R2 API tokens**
5. Click **Create API token**
   - Permissions: Object Read & Write
   - Apply to: Both buckets
6. Copy and save:
   - **Account ID** (shown on the R2 main page, top right)
   - **Access Key ID**
   - **Secret Access Key**
   - **Endpoint URL**: `https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com`

---

## PHASE 3 — Hostinger VPS Initial Setup

### 3.1 — Access your VPS
```bash
# From Hostinger hPanel → VPS → Manage → Access
# Or SSH directly:
ssh root@YOUR_VPS_IP
```

### 3.2 — Create a non-root user (security best practice)
```bash
adduser agribooks
usermod -aG sudo agribooks
# Copy SSH keys
rsync --archive --chown=agribooks:agribooks ~/.ssh /home/agribooks
# Switch to new user for the rest of deployment
su - agribooks
```

### 3.3 — Update and install system packages
```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  git curl wget nano \
  nginx certbot python3-certbot-nginx \
  python3 python3-pip python3-venv \
  supervisor build-essential \
  gnupg ca-certificates
```

### 3.4 — Install Node.js 18 + Yarn
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g yarn
node --version   # should show v18.x
yarn --version
```

### 3.5 — Install MongoDB 7.0
```bash
# Import MongoDB public key
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Add repo
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
  https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

sudo apt update
sudo apt install -y mongodb-org

# Start and enable MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verify it's running
sudo systemctl status mongod
```

### 3.6 — Configure MongoDB (basic security)
```bash
mongosh
# Inside mongosh:
use admin
db.createUser({
  user: "agribooks_admin",
  pwd: "STRONG_PASSWORD_HERE",   # <-- change this
  roles: ["root"]
})
exit
```

Then enable MongoDB auth:
```bash
sudo nano /etc/mongod.conf
# Find the security section and add:
#   security:
#     authorization: enabled
sudo systemctl restart mongod
```

Update your connection string later:
`mongodb://agribooks_admin:STRONG_PASSWORD@localhost:27017/?authSource=admin`

### 3.7 — Install mongodump/mongorestore (for backups)
```bash
sudo apt install -y mongodb-org-tools
mongodump --version   # verify
```

---

## PHASE 4 — Deploy the Application

### 4.1 — Clone from GitHub
```bash
cd /var/www
sudo mkdir agribooks
sudo chown agribooks:agribooks agribooks
git clone https://github.com/YOUR_USERNAME/agribooks.git /var/www/agribooks
cd /var/www/agribooks
```

### 4.2 — Set up Python backend
```bash
cd /var/www/agribooks/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install boto3  # for R2 storage

deactivate
```

### 4.3 — Configure backend environment
```bash
nano /var/www/agribooks/backend/.env
```

Paste and fill in all values:
```env
MONGO_URL=mongodb://agribooks_admin:STRONG_PASSWORD@localhost:27017/?authSource=admin
DB_NAME=agribooks_production
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
JWT_SECRET=GENERATE_WITH_COMMAND_BELOW

RESEND_API_KEY=re_YOUR_RESEND_KEY
SENDER_EMAIL=noreply@yourdomain.com
PLATFORM_ADMIN_EMAIL=your@email.com

R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
R2_BUCKET_NAME=agribooks-backups

BACKUP_SCHEDULE_HOUR=2
BACKUP_RETENTION_DAYS=30
```

Generate a strong JWT secret:
```bash
openssl rand -hex 32
# Copy the output into JWT_SECRET above
```

### 4.4 — Build the React frontend
```bash
cd /var/www/agribooks/frontend

# Set production environment
nano .env
```

Paste:
```env
REACT_APP_BACKEND_URL=https://yourdomain.com
```

Then build:
```bash
yarn install
yarn build
# Creates /var/www/agribooks/frontend/build/
```

---

## PHASE 5 — Configure Supervisor (process manager)

```bash
sudo nano /etc/supervisor/conf.d/agribooks.conf
```

Paste:
```ini
[program:agribooks-backend]
command=/var/www/agribooks/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
directory=/var/www/agribooks/backend
user=agribooks
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/supervisor/agribooks-backend.err.log
stdout_logfile=/var/log/supervisor/agribooks-backend.out.log
environment=PATH="/var/www/agribooks/backend/venv/bin"
```

Apply:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status agribooks-backend
# Should show: RUNNING
```

---

## PHASE 6 — Configure Nginx

### 6.1 — Create site config
```bash
sudo nano /etc/nginx/sites-available/agribooks
```

Paste (replace `yourdomain.com` with your actual domain):
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Increase upload size for receipt images
    client_max_body_size 50M;

    # React frontend (static build)
    root /var/www/agribooks/frontend/build;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # FastAPI backend — all /api/* routes
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
    }

    # Serve uploaded files directly
    location /uploads/ {
        alias /app/uploads/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 6.2 — Enable the site
```bash
sudo ln -s /etc/nginx/sites-available/agribooks /etc/nginx/sites-enabled/
sudo nginx -t        # test config — should say "syntax is ok"
sudo systemctl reload nginx
```

---

## PHASE 7 — Domain DNS Setup

### In Hostinger (or wherever your domain is managed):

Go to **Domains → DNS / Nameservers** and add:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_VPS_IP | 300 |
| A | www | YOUR_VPS_IP | 300 |

Wait 5-15 minutes for DNS to propagate. Test:
```bash
ping yourdomain.com
# Should resolve to YOUR_VPS_IP
```

> **Tip:** If you want to use Cloudflare DNS (recommended for DDoS protection + faster DNS):
> 1. Add your domain to Cloudflare (free plan)
> 2. Change Hostinger nameservers to Cloudflare's
> 3. Add the A records in Cloudflare DNS
> 4. Keep proxy OFF (grey cloud) during SSL setup, then turn ON after

---

## PHASE 8 — SSL Certificate (Free via Let's Encrypt)

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
# Follow the prompts, enter your email
# Choose option 2 (redirect HTTP to HTTPS)
```

Verify auto-renewal:
```bash
sudo certbot renew --dry-run
# Should show: "Congratulations, all simulated renewals succeeded"
```

Certbot auto-renews every 90 days via a systemd timer — nothing else needed.

---

## PHASE 9 — Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Expected output:
```
OpenSSH          ALLOW
Nginx Full       ALLOW   (ports 80 + 443)
```

MongoDB (27017) and backend (8001) are NOT opened externally — only Nginx talks to them internally. This is correct and secure.

---

## PHASE 10 — Final Verification

```bash
# 1. Check all services
sudo systemctl status mongod nginx
sudo supervisorctl status agribooks-backend

# 2. Test the API
curl https://yourdomain.com/health
# Expected: {"status":"healthy","timestamp":"..."}

# 3. Test the app
# Open https://yourdomain.com in your browser
# You should see the AgriBooks landing page

# 4. Test backend
curl https://yourdomain.com/api/organizations/plans
# Should return JSON with plan data
```

---

## PHASE 11 — Post-Launch Security (do before onboarding customers)

```bash
# 1. Run the database migration (auto-runs on first startup)
# Just visit https://yourdomain.com — the startup job handles it

# 2. Create the super admin (also auto-runs on startup)
# Then visit https://yourdomain.com/admin to set up TOTP

# 3. Change the default DB name in .env to something non-obvious
#    DB_NAME=agribooks_prod_2026  (already set above)

# 4. Set up a cron to check supervisor is alive
(crontab -l 2>/dev/null; echo "*/5 * * * * sudo supervisorctl status agribooks-backend | grep -v RUNNING && sudo supervisorctl restart agribooks-backend") | crontab -
```

---

## Updating the App (future deploys)

```bash
cd /var/www/agribooks

# Pull latest code
git pull origin main

# Rebuild frontend if changed
cd frontend && yarn build && cd ..

# Reinstall backend deps if requirements.txt changed
cd backend && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ..

# Restart backend (frontend is auto-served from static build)
sudo supervisorctl restart agribooks-backend
```

---

## Environment Variables Reference (backend/.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_URL` | MongoDB connection string | `mongodb://user:pass@localhost:27017/?authSource=admin` |
| `DB_NAME` | Database name | `agribooks_production` |
| `JWT_SECRET` | 64-char hex string (use `openssl rand -hex 32`) | `a3f8...` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | `https://yourdomain.com` |
| `RESEND_API_KEY` | Resend.com API key for emails | `re_...` |
| `SENDER_EMAIL` | From email address | `noreply@yourdomain.com` |
| `PLATFORM_ADMIN_EMAIL` | Super admin email | `you@email.com` |
| `R2_ACCOUNT_ID` | Cloudflare account ID | `abc123...` |
| `R2_ACCESS_KEY_ID` | R2 API token key | `...` |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret | `...` |
| `R2_ENDPOINT_URL` | R2 S3-compatible endpoint | `https://ID.r2.cloudflarestorage.com` |
| `R2_BUCKET_NAME` | R2 bucket for backups | `agribooks-backups` |
| `BACKUP_SCHEDULE_HOUR` | Hour for daily backup (UTC) | `2` (2 AM UTC) |
| `BACKUP_RETENTION_DAYS` | How many days to keep local backups | `30` |

---

## Troubleshooting

**Backend not starting:**
```bash
sudo supervisorctl tail agribooks-backend stderr
# Check logs for Python errors
```

**502 Bad Gateway from Nginx:**
```bash
sudo supervisorctl status agribooks-backend
# If not RUNNING:
sudo supervisorctl restart agribooks-backend
```

**MongoDB connection refused:**
```bash
sudo systemctl status mongod
sudo systemctl restart mongod
```

**SSL certificate issues:**
```bash
sudo certbot certificates       # check expiry
sudo certbot renew              # force renew
```

**Frontend showing old version after update:**
```bash
cd /var/www/agribooks/frontend
yarn build
# Nginx serves static files directly, no restart needed
```
