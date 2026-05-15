# AI Pipeline Triage Agent

Simulates CI/CD pipeline failures (Playwright E2E tests and EKS deployments), uploads failure logs to GitHub Gists, and triggers a GitHub Actions workflow that uses an AI agent to generate a Root Cause Analysis (RCA), auto-create GitHub Issues, and post results to Microsoft Teams.

---

## How it works

```
GitHub Actions (simulate.yml)              GitHub Actions (triage.yml / pipeline-failure)
─────────────────────────────              ──────────────────────────────────────────────
simulate-eks job             ─dispatch─►  triage.yml
  (workflow_dispatch / cron)                 │
  category: "eks-deploy"                     ▼
                                           Python triage_agent.py
simulate-playwright job      ─dispatch─►    ├─ Fetches log from Gist raw URL
  (workflow_dispatch)                        ├─ Calls GitHub Models (gpt-4o)
  category: "playwright-e2e"                 ├─ Tool-calling loop:
                                             │    check_duplicate_issue
─ OR ─                                       │    create_github_issue / add_issue_comment
                                             ├─ Prints RCA to Actions log
Local Machine                                └─ Sends Adaptive Card to Teams
─────────────
./run_and_triage.sh          ─dispatch─►  (same triage.yml above)
./simulate_eks_failure.sh    ─dispatch─►
```

---

## Prerequisites

- Node.js (v18+)
- Python 3.x
- A GitHub account with access to this repository

---

## Step 1 — Create a GitHub Personal Access Token (Classic)

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token → Generate new token (classic)**
3. Fill in:
   - **Note:** `pipeline-triage`
   - **Expiration:** 90 days (or as needed)
4. Under **Select scopes**, tick:
   - `repo` — full repository access (needed to trigger GitHub Actions)
   - `gist` — create and delete Gists (needed to upload logs)
5. Click **Generate token**
6. **Copy the token immediately** — GitHub only shows it once

---

## Step 2 — Create your `.env` file

In the project root, copy the example file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=pramodhkumars7/ai-jenkins-pipeline-triage
```

> `.env` is gitignored — it will never be committed. Each team member keeps their own `.env` with their own PAT.

---

## Step 3 — Install dependencies

```bash
npm install
```

---

## Step 4 — Install Playwright browsers

```bash
npx playwright install chromium
```

---

## Step 5a — Run the Playwright triage script

```bash
./run_and_triage.sh
```

The script will:

1. Run all Playwright tests
2. Print test output to the terminal
3. On failure — upload the full log to a secret GitHub Gist
4. Trigger the GitHub Actions triage workflow
5. Print the Gist URL and Actions link

---

## Step 5b — Simulate an EKS deploy failure

```bash
./simulate_eks_failure.sh
```

Or pick a specific scenario:

```bash
./simulate_eks_failure.sh CrashLoopBackOff
./simulate_eks_failure.sh OOMKilled
./simulate_eks_failure.sh ImagePullBackOff
./simulate_eks_failure.sh ReadinessProbeFailed
```

This generates a realistic `kubectl` failure log, uploads it to a secret Gist, and dispatches a `pipeline-failure` event with `category: "eks-deploy"`. The Actions workflow runs the same triage agent and creates a labeled GitHub Issue.

---

## GitHub Actions secrets (repo admin sets these once)

Go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Required | Description |
|---|---|---|
| `TEAMS_WEBHOOK` | Yes | Incoming webhook URL from your Teams channel (via Workflows) |
| `PAT_TOKEN_1` | For simulate.yml | Fine-grained PAT for team member 1 (`repo` + Gist account permission). Used on days where `(day-1) % 3 == 0`. |
| `PAT_TOKEN_2` | For simulate.yml | Fine-grained PAT for team member 2. Used on days where `(day-1) % 3 == 1`. |
| `PAT_TOKEN_3` | For simulate.yml | Fine-grained PAT for team member 3. Used on days where `(day-1) % 3 == 2`. |

> `GITHUB_TOKEN` is auto-injected by GitHub Actions — no setup needed for `triage.yml`.
> `PAT_TOKEN_1/2/3` are required only for `simulate.yml`. The auto-injected token cannot create Gists, so a PAT with `gist` (account) permission is needed. The rotation spreads GitHub Models token usage across all three team members.
> For local runs, each developer uses their own PAT in `.env` — no shared credentials.

---

## Step 6 — Trigger the demo from GitHub Actions (no local machine needed)

This is the easiest way to demo — everything runs in the cloud.

### One-time setup (repo admin)

1. Each team member creates a fine-grained PAT (see Step 1 — use fine-grained, not classic):
   - **Resource owner:** your GitHub account
   - **Repository access:** Only `pramodhkumars7/ai-jenkins-pipeline-triage`
   - **Permissions → Repository:** `Contents: Read`, `Issues: Read/Write`, `Metadata: Read`
   - **Permissions → Account:** `Gists: Read/Write`
2. Share the PAT with the repo admin (e.g. via Teams DM — don't commit it)
3. Admin adds them as secrets: **Settings → Secrets and variables → Actions → New repository secret**
   - `PAT_TOKEN_1` — team member 1's PAT
   - `PAT_TOKEN_2` — team member 2's PAT
   - `PAT_TOKEN_3` — team member 3's PAT

### Running the demo

1. Go to **Actions → Simulate Pipeline Failure → Run workflow**
2. Choose:
   - **Failure category:** `eks-deploy` or `playwright-e2e`
   - **EKS scenario:** `random`, `CrashLoopBackOff`, `OOMKilled`, `ImagePullBackOff`, or `ReadinessProbeFailed` (ignored for Playwright)
3. Click **Run workflow**
4. The `simulate-eks` (or `simulate-playwright`) job generates a log, uploads it to a Gist, and dispatches the `pipeline-failure` event
5. The **Pipeline Triage Agent** workflow fires automatically — watch it create a GitHub Issue and (if configured) post to Teams

A daily smoke test also runs automatically at **08:00 UTC** (EKS/random scenario).

---

## Getting the Teams webhook URL

1. Open Teams → go to the channel for notifications
2. Click **···** next to the channel name → **Workflows**
3. Search: `Post to a channel when a webhook request is received`
4. Click it → Next → select your team and channel → **Add workflow**
5. Copy the webhook URL and add it as the `TEAMS_WEBHOOK` secret above

---

## Project structure

```
├── src/
│   ├── index.html           # Home page
│   ├── login.html           # Login page
│   └── dashboard.html       # Dashboard page
├── tests/
│   ├── home.spec.js         # Playwright tests (intentionally failing for demo)
│   ├── login.spec.js
│   ├── dashboard.spec.js
│   ├── test_agent_tools.py  # Unit tests for GitHub Issue helpers
│   ├── test_triage_agent.py # Unit tests for tool-calling loop and prompt builder
│   └── test_gen_eks_log.py  # Unit tests for EKS log generator
├── scripts/
│   └── gen_eks_log.py       # Synthetic EKS failure log generator (4 scenarios)
├── prompts/
│   └── agent_prompt.md      # Shared agent prompt template with category branching
├── .github/
│   └── workflows/
│       ├── simulate.yml     # Trigger EKS/Playwright failures from Actions (no local machine)
│       └── triage.yml       # AI triage agent workflow (fires on pipeline-failure event)
├── triage_agent.py          # AI triage agent with tool-calling (runs in Actions)
├── agent_tools.py           # GitHub Issue create / dedup / comment helpers
├── run_and_triage.sh        # Playwright failure dispatcher
├── simulate_eks_failure.sh  # EKS failure dispatcher
├── requirements.txt         # Pinned Python dependencies
├── playwright.config.js
├── package.json
├── .env.example             # Template for your .env
└── .gitignore
```

---

## Notes

- Each developer uses their own PAT in `.env` — no shared credentials
- GitHub Gists are automatically cleaned up: each run deletes the previous run's Gist before creating a new one
- The triage agent uses `gpt-4o` from GitHub Models — no external API key needed
