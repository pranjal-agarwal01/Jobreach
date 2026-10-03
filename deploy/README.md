# Deploying Jobreach (free): one Oracle Cloud server

Everything runs on one always-free Oracle Cloud server: the web app, the API, the worker, and
Caddy in front, which gets the HTTPS certificate by itself. The database and sign-in stay on
Supabase's free plan.

    https://jobreach.pranjalagarwal.me/        the web app
    https://jobreach.pranjalagarwal.me/api/... the API

Cost: nothing. Oracle's Always Free allowance (2 ARM CPUs and 12 GB of memory) is far more than
Jobreach needs; Supabase's free plan stays awake because the worker uses the database all the
time.

## 1. Oracle Cloud: the server (your part, about 15 minutes)

1. Sign up at https://www.oracle.com/cloud/free/. A card is asked for to verify you; Always Free
   resources are not charged. **Home region:** India West (Mumbai) or India South (Hyderabad).
   It can't be changed later.
2. Compute > Instances > **Create instance**:
   - Image: **Canonical Ubuntu 24.04** (the aarch64 build is picked with the shape below).
   - Shape: Ampere > **VM.Standard.A1.Flex**, **2 OCPUs, 12 GB memory** (the free allowance).
   - Networking: the default new network, **with a public IPv4 address**.
   - SSH keys: **Generate a key pair** and **download the private key**. Keep it safe: it is
     the only way into the server.
   - Create. If it says "Out of capacity", try again later or in another availability domain
     (free ARM servers are popular). Upgrading the account to Pay As You Go keeps Always Free
     resources free and usually ends the capacity errors.
3. Open the web ports: on the instance page, open its **subnet** > **Default Security List** >
   **Add Ingress Rules**, twice: source `0.0.0.0/0`, TCP, destination port `80`; and the same
   for `443`.
4. Copy the instance's **public IP address**.

## 2. Namecheap: the address (your part, 2 minutes)

Domain List > pranjalagarwal.me > **Advanced DNS** > Add new record:

| Type | Host | Value | TTL |
|---|---|---|---|
| A Record | `jobreach` | the server's public IP | Automatic |

## 3. Google Cloud and Supabase: allow the new address (your part, 5 minutes)

- Google Cloud > Clients > your web client:
  - Authorized JavaScript origins: add `https://jobreach.pranjalagarwal.me`
  - Authorized redirect URIs: add `https://jobreach.pranjalagarwal.me/api/gmail/callback`
  (keep the localhost entries for local testing).
- Supabase > Authentication > URL Configuration: Site URL `https://jobreach.pranjalagarwal.me`;
  Redirect URLs: add `https://jobreach.pranjalagarwal.me/**` (keep `http://localhost:3000/**`).

## 4. Ship it (from this PC)

```bash
python deploy/make_env.py
bash deploy/ship.sh <server IP> <path to the downloaded private key>
```

`make_env.py` writes `deploy/.env` (git-ignored) from `backend/.env` and `frontend/.env.local`
with the deployed addresses. `ship.sh` copies the last commit and that file to the server, then
runs `deploy/setup.sh` there: Docker is installed the first time, the web ports are opened in the
server's own firewall, and everything is built and started. The first build takes 5 to 10
minutes. Updating later is the same `ship.sh` command.

Then stop the API and the worker on your PC: the server's now do the work, and the database's
connection pool is shared.

## Looking after it

```bash
ssh -i <key> ubuntu@<server IP>
cd ~/jobreach/src/deploy
sudo docker compose ps                 # what is running
sudo docker compose logs -f worker     # the worker's log (api, web, caddy likewise)
sudo docker compose restart worker
```

Ubuntu installs security updates by itself. Containers restart on their own after a crash or a
reboot.
