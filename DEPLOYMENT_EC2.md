# 🚀 Complete AWS EC2 Deployment Guide
### MCP Enterprise Data Analyst — Production Deployment with Docker Compose & Nginx

This guide walks you step-by-step through deploying the **MCP Enterprise Data Analyst** application on an **AWS EC2 (Ubuntu Linux)** virtual machine.

---

## 📋 Table of Contents
1. [EC2 Instance Sizing & Architecture](#1-ec2-instance-sizing--architecture)
2. [AWS EC2 Provisioning (Step-by-Step)](#2-aws-ec2-provisioning-step-by-step)
3. [Connecting to Your EC2 Instance](#3-connecting-to-your-ec2-instance)
4. [Server Preparation & 4GB Swap Space](#4-server-preparation--4gb-swap-space)
5. [Installing Docker & Docker Compose](#5-installing-docker--docker-compose)
6. [Cloning the Code & Configuring `.env`](#6-cloning-the-code--configuring-env)
7. [Launching the Stack via Docker Compose](#7-launching-the-stack-via-docker-compose)
8. [Configuring Nginx Reverse Proxy (Domain & Port 80)](#8-configuring-nginx-reverse-proxy-domain--port-80)
9. [Securing with Free HTTPS (Let's Encrypt SSL)](#9-securing-with-free-https-lets-encrypt-ssl)
10. [Updating the Application & Monitoring Logs](#10-updating-the-application--monitoring-logs)
11. [Troubleshooting & FAQs](#11-troubleshooting--faqs)

---

## 1. EC2 Instance Sizing & Architecture

The stack consists of 3 microservices:
1. **FastAPI Application** (Python 3.11 + LangGraph + Uvicorn)
2. **MySQL 8.4** (Transactional database with 5,300+ orders)
3. **ChromaDB 0.5.5** (Vector database + Embeddings)

### Recommended Sizing:
| Specification | Recommendation | Notes |
|---|---|---|
| **Instance Type** | `t3.medium` (2 vCPU, 4 GB RAM) | Ideal for production performance. |
| **Budget Alternative** | `t3.small` (2 vCPU, 2 GB RAM) | Requires setting up 4GB Swap Space (covered in Step 4). |
| **Operating System** | **Ubuntu 24.04 LTS** or **22.04 LTS (x86_64)** | Cleanest Docker support. |
| **Storage (EBS)** | 25 - 30 GB `gp3` SSD | Docker images, MySQL volumes, and ChromaDB vector persistence. |

---

## 2. AWS EC2 Provisioning (Step-by-Step)

1. Log into your **AWS Management Console** and navigate to **EC2** $\rightarrow$ **Instances** $\rightarrow$ **Launch instances**.
2. **Name**: `mcp-enterprise-analyst-prod`
3. **Application and OS Images (AMI)**: Choose **Ubuntu Server 24.04 LTS (HVM), SSD Volume Type**.
4. **Instance Type**: Select **`t3.medium`** (or `t3.small`).
5. **Key Pair (login)**:
   - Select an existing key pair or click **Create new key pair** (e.g. `analyst-key.pem`).
   - Download and save the `.pem` file safely.
6. **Network settings (Security Group)**:
   Click **Edit** and configure the following inbound rules:

| Type | Protocol | Port Range | Source | Purpose |
|---|---|---|---|---|
| **SSH** | TCP | `22` | `My IP` (or `0.0.0.0/0`) | Secure Terminal Access |
| **HTTP** | TCP | `80` | `0.0.0.0/0` (Anywhere) | Public Web UI Traffic |
| **HTTPS** | TCP | `443` | `0.0.0.0/0` (Anywhere) | Secure Encrypted Traffic |
| **Custom TCP** | TCP | `8000` | `0.0.0.0/0` (Anywhere) | Direct FastAPI Testing (Optional) |

7. **Configure Storage**: Change the root volume size from `8 GiB` to **`25 GiB` (gp3)**.
8. Click **Launch Instance**. Wait 1–2 minutes until the status checks show *Running*.

---

## 3. Connecting to Your EC2 Instance

### From Windows (PowerShell) / Mac / Linux:
Navigate to the directory where your `.pem` key was downloaded:

```bash
# On Linux/macOS only (set permissions):
chmod 400 analyst-key.pem

# SSH into the server:
ssh -i "analyst-key.pem" ubuntu@<YOUR-EC2-PUBLIC-IP>
```
*(Replace `<YOUR-EC2-PUBLIC-IP>` with your instance's Public IPv4 address from the AWS Console).*

---

## 4. Server Preparation & 4GB Swap Space

To guarantee that the machine never crashes due to Out-Of-Memory (OOM) errors during container builds or data indexing:

```bash
# 1. Update package lists & existing packages
sudo apt update && sudo apt upgrade -y

# 2. Create a 4 GB Swap File
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 3. Make swap permanent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 4. Verify swap is active
free -h
```

---

## 5. Installing Docker & Docker Compose

Run the official Docker installation commands for Ubuntu:

```bash
# 1. Install prerequisite utilities
sudo apt install -y ca-certificates curl gnupg lsb-release git

# 2. Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# 3. Add Docker repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Install Docker Engine and Docker Compose plugin
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Add 'ubuntu' user to docker group (run without sudo)
sudo usermod -aG docker $USER

# 6. Apply group changes immediately
newgrp docker

# 7. Test Docker installation
docker --version
docker compose version
```

---

## 6. Cloning the Code & Configuring `.env`

```bash
# 1. Clone your GitHub repository
cd /home/ubuntu
git clone https://github.com/bittush8789/mcp-enterprise-data-analyst.git

# 2. Enter project directory
cd mcp-enterprise-data-analyst

# 3. Create your production .env file
cp .env.example .env

# 4. Edit the .env file
nano .env
```

In `nano`, fill in your actual **`GROQ_API_KEY`**:
```env
# Groq API Configuration
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Database & Chroma settings (used inside docker network)
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=enterprise_analytics
MYSQL_USER=root
MYSQL_PASSWORD=root

CHROMA_HOST=chromadb
CHROMA_PORT=8000

SEMANTIC_WEIGHT=0.6
KEYWORD_WEIGHT=0.4
TOP_K=5
MAX_ROWS=1000
QUERY_TIMEOUT=10
LOG_LEVEL=INFO
```
*Press `Ctrl + O` then `Enter` to save, and `Ctrl + X` to exit `nano`.*

---

## 7. Launching the Stack via Docker Compose

Run the multi-container stack in detached background mode:

```bash
# Build images and start all 3 services (mysql, chromadb, backend)
docker compose up -d --build
```

### Verify Running Containers:
```bash
docker compose ps
```
You should see:
- `enterprise_mysql` — Port `3306/tcp` (healthy)
- `enterprise_chromadb` — Port `8001->8000/tcp` (healthy)
- `enterprise_backend` — Port `0.0.0.0:8000->8000/tcp`

### Inspect Application Logs:
```bash
docker compose logs -f backend
```
*(Press `Ctrl + C` to exit logs).*

### Test the Endpoint:
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{"status":"healthy","components":{"fastapi":"healthy","mysql":"healthy","chromadb":"healthy","llm_engine":"groq (openai/gpt-oss-120b)"}}
```

> **Direct Access Test**: Open `http://<YOUR-EC2-PUBLIC-IP>:8000` in your web browser. Your application is live!

---

## 8. Configuring Nginx Reverse Proxy (Domain & Port 80)

To serve the app cleanly on standard HTTP/HTTPS ports (80/443) without typing `:8000` in the URL:

```bash
# 1. Install Nginx
sudo apt install -y nginx

# 2. Create Nginx reverse proxy configuration
sudo nano /etc/nginx/sites-available/enterprise-analyst
```

Paste the following configuration:
```nginx
server {
    listen 80;
    server_name _;  # Replace with your domain name (e.g. analyst.yourcompany.com) if you have one

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
# 3. Enable site & test configuration
sudo ln -s /etc/nginx/sites-available/enterprise-analyst /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

# 4. Restart Nginx
sudo systemctl restart nginx
```

Now open:  
👉 `http://<YOUR-EC2-PUBLIC-IP>` (No `:8000` needed!)

---

## 9. Securing with Free HTTPS (Let's Encrypt SSL)

If you have a domain name pointed to your EC2 Public IP:

```bash
# 1. Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# 2. Generate free SSL certificate & auto-configure Nginx
sudo certbot --nginx -d analyst.yourdomain.com

# 3. Follow prompts to enter email and agree to terms.
```
Certbot will configure auto-renewal via a systemd timer automatically.

---

## 10. Updating the Application & Monitoring Logs

### Pulling Latest Updates from GitHub:
When you push new changes to GitHub:

```bash
cd /home/ubuntu/mcp-enterprise-data-analyst

# Pull new commits
git pull origin main

# Rebuild and restart only updated containers
docker compose up -d --build
```

### Helpful Commands:
```bash
# View live logs of all services
docker compose logs -f

# View live backend logs only
docker compose logs -f backend

# Restart the application
docker compose restart

# Stop all containers
docker compose down

# Check disk usage
df -h
docker system df
```

---

## 11. Troubleshooting & FAQs

### Q1: The browser says "Connection Refused" or page doesn't load.
- **Cause**: Security Group rule missing.
- **Fix**: Go to AWS Console $\rightarrow$ EC2 $\rightarrow$ Instances $\rightarrow$ Security $\rightarrow$ Security Groups. Ensure inbound rules for **Port 80** and **Port 8000** have source `0.0.0.0/0`.

### Q2: MySQL container fails to start or healthcheck loops.
- **Cause**: Insufficient memory or volume conflict.
- **Fix**: Check logs with `docker compose logs mysql`. Ensure you configured the 4GB Swap Space from Step 4.

### Q3: Groq LLM says "Invalid API Key" or rate limit.
- **Cause**: `.env` file does not contain valid key.
- **Fix**: Run `nano .env`, verify `GROQ_API_KEY=gsk_...`, and restart backend with `docker compose restart backend`.

### Q4: How do I re-ingest documents on the server?
- **Fix**: Execute into the running backend container:
```bash
docker compose exec backend python -c "from backend.chroma import chroma_manager; chroma_manager.ingest_documents(force=True)"
```
