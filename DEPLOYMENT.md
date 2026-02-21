# AgriPOS — Production Deployment Guide
## Hostinger VPS + Cloudflare DNS/SSL + Cloudflare R2

---

## Prerequisites

| Requirement | Recommendation |
|-------------|----------------|
| VPS | Hostinger **KVM 4** (4 vCPU / 16GB RAM / 200GB NVMe) |
| OS | Ubuntu 22.04 LTS |
| Domain | Any registrar — use Cloudflare for DNS |
| SSL | Cloudflare (handles HTTPS automatically) |
| Backup storage | Cloudflare R2 (first 10GB/month free) |

---

## Step 1 — Buy and Set Up Hostinger VPS

1. Purchase **KVM 4** plan at hostinger.com
2. Choose **Ubuntu 22.04 LTS**
3. Set a strong root password (or use SSH key — recommended)
4. Note your VPS **IP address**

**SSH into your VPS:**
```bash
ssh root@YOUR_VPS_IP
```

---

## Step 2 — Install Docker on the VPS

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt install -y docker-compose-plugin

# Verify
docker --version
docker compose version
```

---

## Step 3 — Copy the App to the VPS

**Option A — Git (recommended):**
```bash
# On VPS
git clone https://github.com/YOUR_USERNAME/agripos.git /opt/agripos
cd /opt/agripos
```

**Option B — SCP from your computer:**
```bash
# On your local machine
scp -r /path/to/agripos root@YOUR_VPS_IP:/opt/agripos
```

---

## Step 4 — Configure Environment Variables

```bash
cd /opt/agripos

# Copy the template
cp .env.production .env

# Edit with your values
nano .env
```

**Fill in these values:**

```env
MONGO_URL=mongodb://mongodb:27017
DB_NAME=agripos_production

# Generate strong secret:  openssl rand -hex 32
JWT_SECRET=PASTE_YOUR_GENERATED_SECRET_HERE

CORS_ORIGINS=https://yourdomain.com
REACT_APP_BACKEND_URL=https://yourdomain.com

# From Cloudflare R2 dashboard
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_BUCKET_NAME=agripos-backups

BACKUP_RETENTION_DAYS=30
BACKUP_SCHEDULE_HOUR=1
```

**Generate your JWT secret:**
```bash
openssl rand -hex 32
# Copy the output into JWT_SECRET above
```

---

## Step 5 — Build and Start

```bash
cd /opt/agripos

# Build and start all services
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f
```

**First-time startup takes 3–5 minutes** (Docker builds the React app and backend).

---

## Step 6 — Configure Cloudflare DNS

1. Go to **Cloudflare Dashboard → your domain → DNS**
2. Add an **A record**:
   - **Name**: `@` (or `app` for subdomain like `app.yourdomain.com`)
   - **IPv4 address**: your VPS IP
   - **Proxy status**: ☁️ Proxied (orange cloud ON)
3. Add a **CNAME** for `www`:
   - **Name**: `www`
   - **Target**: `yourdomain.com`
   - **Proxy status**: Proxied

**SSL/TLS Settings** (Cloudflare Dashboard → SSL/TLS):
- Set mode to **Full** (not Strict — VPS only has HTTP)

Wait 1–2 minutes for DNS to propagate.

---

## Step 7 — Set Up Cloudflare R2 Backup Bucket

1. Go to **Cloudflare Dashboard → R2 → Create bucket**
2. Name it `agripos-backups`
3. Go to **R2 → Manage API Tokens → Create API Token**
4. Choose **Object Read & Write** on the `agripos-backups` bucket only
5. Copy **Access Key ID** and **Secret Access Key** to your `.env` file
6. Restart the backend: `docker compose restart backend`

---

## Step 8 — First Login and Setup

1. Visit `https://yourdomain.com`
2. You'll see the Setup Wizard (first time only)
3. Create your admin account
4. Create branches, add users, import products

---

## Maintenance

### Update the app (deploy new version):
```bash
cd /opt/agripos
git pull
docker compose up -d --build
```

### View logs:
```bash
docker compose logs backend    # Backend logs
docker compose logs frontend   # Frontend/nginx logs
docker compose logs mongodb    # Database logs
```

### Stop / restart:
```bash
docker compose down         # Stop all
docker compose restart      # Restart all
docker compose restart backend  # Restart just backend
```

### Manual backup:
```bash
# Via API (logged in as admin):
curl -X POST https://yourdomain.com/api/backups/create \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Restore from backup:
```bash
# List available backups
curl https://yourdomain.com/api/backups/list \
  -H "Authorization: Bearer YOUR_TOKEN"

# Restore (WARNING: overwrites current data)
curl -X POST https://yourdomain.com/api/backups/restore/FILENAME.archive.gz \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### MongoDB backup (manual, direct):
```bash
docker exec agripos-mongodb mongodump --db agripos_production --out /tmp/backup
docker cp agripos-mongodb:/tmp/backup ./manual-backup
```

---

## Monitoring

### Check disk usage:
```bash
df -h
du -sh /var/lib/docker/volumes/agripos_mongodb_data
du -sh /opt/agripos/backups
```

### Check memory:
```bash
free -h
docker stats
```

---

## Firewall (Optional but Recommended)

```bash
# Allow SSH, HTTP, HTTPS only
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# MongoDB and backend are internal — no external access needed
```

---

## Performance Notes

- **3000 SKUs, 20 branches**: KVM 4 handles this comfortably
- **Offline mode**: Cashiers cache data locally — works even on slow connections
- **MongoDB**: Runs on NVMe SSD — fast queries
- **React build**: Served by nginx with gzip + browser caching

---

## Estimated Monthly Costs

| Service | Cost |
|---------|------|
| Hostinger KVM 4 | ~$15–25/month |
| Cloudflare (DNS + SSL) | Free |
| Cloudflare R2 (10GB free) | Free (or ~$0.015/GB after) |
| **Total** | **~$20/month** |
