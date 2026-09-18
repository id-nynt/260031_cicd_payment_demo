# Payment service

## 1. Local run

Actions:

- Start Docker Desktop.
- Build and start app + PostgreSQL.
- Open the checkout UI.
- Make a fake payment.
- Check /health and /ready.
- Run the existing quality checks.

Commands:

```
docker compose up -d --build
docker compose ps

# Then:
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

## 2. Setup GitHub Actions self-hosted runner

### 2.1. Create GitHub repo

- Create GitHub repo for this project
- Connect to local project

```
git init
git add .
git commit -m "Initial payment service"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/payment-service.git
git push -u origin main
```

- Check tab Actions: if there is the workflow

### 2.2. Install the self-hosted runner

1. If the runner is NOT installed:
   - Go to GitHub repository → Settings → Actions → Runners → New self-hosted runner.
   - Select Linux → x64.
   - Follow GitHub's provided commands to download and configure the runner.
   - Start it with:

   ```
   ./run.sh
   ```

   - Check GitHub → Settings → Actions → Runners → runner should show Idle/Online.

2. If the runner IS already installed in Ubuntu/WSL:
   - Open PowerShell and start Ubuntu:

   ```
   wsl -d Ubuntu
   ```

   - Go to the existing runner:

   ```
   cd ~/actions-runner
   ls
   ```

   - Start/activate it:

   ```
   ./run.sh
   ```

   - Expected:

   ```
   Connected to GitHub
   Listening for Jobs
   ```

   - Check GitHub repository → Settings → Actions → Runners → runner should show Idle/Online.

Checkpoint: ✅ Self-hosted runner is online and waiting for GitHub Actions jobs.
