# GitHub Secrets Configuration Guide

This document provides comprehensive guidance for configuring all required and optional GitHub Secrets for the BMAD Wyckoff Trading System CI/CD pipeline.

## Overview

GitHub Secrets are encrypted environment variables that provide secure access to sensitive data in workflows. This system uses 7 secrets across multiple CI/CD workflows for testing, building, deploying, and notifications.

**Key Principles:**
- REQUIRED secrets must be configured before any workflow can run
- OPTIONAL secrets gracefully degrade (workflows skip or warn but don't fail)
- Never commit secret values to the repository
- Rotate credentials periodically according to security policies
- Use separate credentials for each environment (dev, staging, production)

## Secrets Reference Table

| Secret | Requirement | Description | Source | Rotation | Workflows |
|--------|-------------|-------------|--------|----------|-----------|
| `TEST_DB_PASSWORD` | **REQUIRED** | PostgreSQL test database password for running tests in CI | Generate manually | Every 90 days | PR CI, Main CI, Deploy, Benchmarks, Monthly Regression |
| `CODECOV_TOKEN` | OPTIONAL | Codecov API token for uploading coverage reports | Codecov.io dashboard | Every 180 days | PR CI, Main CI |
| `GITHUB_TOKEN` | AUTOMATIC | GitHub Actions token (auto-generated per workflow run) | GitHub Actions | Per workflow | All workflows using `actions/github-script` |
| `DOCKER_USERNAME` | **REQUIRED** (deploy only) | Docker Hub username for image push authentication | Docker Hub account | Never* | Deploy only |
| `DOCKER_PASSWORD` | **REQUIRED** (deploy only) | Docker Hub personal access token/password | Docker Hub account | Every 180 days | Deploy only |
| `SLACK_WEBHOOK_URL` | OPTIONAL | Slack incoming webhook for notifications | Slack workspace | Every 365 days | Main CI (commented), Monthly Regression |
| `CLAUDE_CODE_OAUTH_TOKEN` | **REQUIRED** | Claude Code authentication token for AI-assisted workflows | Anthropic Claude Code | Every 180 days | Claude interactive, Claude code-review |

*Docker usernames change infrequently; only update if account is compromised

## Detailed Setup Instructions

### 1. TEST_DB_PASSWORD (REQUIRED)

This password is used by PostgreSQL in Docker services during CI test runs. It must be set for any testing workflow to function.

**Where It's Used:**
- All test database initialization steps
- Connection string construction in environment variables
- Database health checks in service containers

**Setup Steps:**

1. Generate a strong password (minimum 16 characters, include uppercase, lowercase, numbers, special characters)
   ```bash
   # Example strong password generation (do NOT use these exact passwords)
   openssl rand -base64 16
   ```

2. Navigate to your GitHub repository settings:
   - Go to `Settings` → `Secrets and variables` → `Actions`

3. Click `New repository secret`

4. Enter:
   - Name: `TEST_DB_PASSWORD`
   - Value: Your generated password (paste, don't type)

5. Click `Add secret`

6. Verify in workflow logs (will show as `***` when used)

**Security Notes:**
- Use a different password for each environment (dev, staging, production)
- Document the password in a secure password manager (e.g., 1Password, LastPass)
- Never share via unencrypted channels
- Rotate every 90 days to limit exposure window

**How to Rotate:**
1. Generate new password
2. Update secret value in GitHub Actions secrets
3. Verify all test workflows pass with new password
4. Update any local development `.env` files

### 2. CODECOV_TOKEN (OPTIONAL)

This token enables automatic code coverage report uploads to Codecov.io. Without it, coverage upload steps will show warnings but workflows continue.

**Where It's Used:**
- PR CI workflow: Backend and frontend coverage uploads
- Main CI workflow: Extended coverage tracking

**Setup Steps:**

1. Visit [codecov.io](https://codecov.io)

2. Sign up or log in with your GitHub account

3. Select your repository from the dashboard

4. Navigate to Settings:
   - Click your repository name
   - Go to `Settings`
   - Copy the Repository Token (typically a UUID format)

5. Add to GitHub Secrets:
   - Go to repository `Settings` → `Secrets and variables` → `Actions`
   - Click `New repository secret`
   - Name: `CODECOV_TOKEN`
   - Value: Your Codecov repository token

6. Click `Add secret`

**Verification:**
- Next PR will show coverage badge/link in workflow summary
- Visit codecov.io to see coverage history and trends

**Security Notes:**
- Repository tokens are scoped to specific repositories
- Rotate annually as security best practice
- Codecov can regenerate tokens if compromised

### 3. GITHUB_TOKEN (AUTOMATIC)

This is automatically provided by GitHub Actions for each workflow run. It requires no manual setup.

**Scope:**
- Read access to repository contents
- Write access to pull requests and issues
- Action execution permissions

**Default Behavior:**
- Automatically available as `secrets.GITHUB_TOKEN`
- Scoped only to the current repository
- Expires after workflow completes
- Cannot be rotated (auto-managed by GitHub)

**Used For:**
- Gitleaks secret scanning (environment variable only)
- Creating GitHub issues on regression detection
- Posting comments on pull requests
- Reading PR context in Claude workflows

**No Configuration Needed** - provided by default.

### 4. DOCKER_USERNAME (REQUIRED for Deployment)

Docker Hub username for authenticating Docker image pushes during deployment workflow.

**Where It's Used:**
- Deploy workflow: Docker Hub authentication
- Image push validation steps
- Registry authentication

**Setup Steps:**

1. Ensure you have a Docker Hub account:
   - Go to [hub.docker.com](https://hub.docker.com)
   - Create account or log in

2. Verify you have access to push to target repositories:
   - Confirm you own or have write access to `bmad-wyckoff-backend` and `bmad-wyckoff-frontend` repos

3. Add to GitHub Secrets:
   - Go to repository `Settings` → `Secrets and variables` → `Actions`
   - Click `New repository secret`
   - Name: `DOCKER_USERNAME`
   - Value: Your Docker Hub username

4. Click `Add secret`

**Example:**
```
DOCKER_USERNAME: john_developer
DOCKER_PASSWORD: <personal-access-token>
```

**Security Notes:**
- Never use your primary Docker Hub password
- Use a Personal Access Token (PAT) with limited scope instead
- Tokens can be created in Docker Hub Account Settings

### 5. DOCKER_PASSWORD (REQUIRED for Deployment)

Docker Hub personal access token (NOT your account password) for authentication.

**Where It's Used:**
- Deploy workflow: Docker image authentication
- Registry push authentication
- Login validation steps

**Setup Steps:**

1. Log in to Docker Hub

2. Navigate to Account Settings:
   - Click your profile icon (top right)
   - Select `Account Settings`

3. Create Personal Access Token:
   - Go to `Security` section
   - Click `New Access Token`
   - Token description: `GitHub Actions BMAD Deployment`
   - Access permissions: Select `Read, Write` (for pushing images)
   - Click `Generate`

4. Copy the token (displayed only once)

5. Add to GitHub Secrets:
   - Go to repository `Settings` → `Secrets and variables` → `Actions`
   - Click `New repository secret`
   - Name: `DOCKER_PASSWORD`
   - Value: Your Docker Hub Personal Access Token (paste, don't type)

6. Click `Add secret`

**Verification:**
- Next deployment workflow run will authenticate successfully
- Check Docker Hub repository for pushed images

**Security Notes:**
- PATs are more secure than account passwords
- Can be revoked individually without affecting other access
- Use minimal scope (read/write for specific repositories)
- Rotate every 180 days

**How to Rotate:**
1. Generate new PAT in Docker Hub
2. Update `DOCKER_PASSWORD` secret in GitHub
3. Verify deployment workflow succeeds
4. Revoke old PAT in Docker Hub Account Settings

### 6. SLACK_WEBHOOK_URL (OPTIONAL)

Webhook URL for sending notifications to Slack channels. Without this, notification steps are skipped.

**Where It's Used:**
- Main CI workflow: Failure notifications (currently commented out)
- Monthly regression workflow: Regression detection alerts

**Setup Steps:**

1. Create Slack Incoming Webhook:
   - Go to your Slack workspace
   - Visit [api.slack.com/apps](https://api.slack.com/apps)
   - Click `Create New App` → `From scratch`
   - App name: `BMAD CI Notifications`
   - Select your workspace
   - Click `Create App`

2. Configure incoming webhooks:
   - In left sidebar, click `Incoming Webhooks`
   - Click toggle to `On`
   - Click `Add New Webhook to Workspace`
   - Select channel (e.g., `#ci-notifications`)
   - Click `Allow`

3. Copy the Webhook URL (format: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`)

4. Add to GitHub Secrets:
   - Go to repository `Settings` → `Secrets and variables` → `Actions`
   - Click `New repository secret`
   - Name: `SLACK_WEBHOOK_URL`
   - Value: Your Slack Webhook URL

5. Click `Add secret`

**Verification:**
- You can test the webhook manually:
  ```bash
  curl -X POST -H 'Content-type: application/json' \
    --data '{"text":"Test notification from BMAD CI"}' \
    <YOUR_WEBHOOK_URL>
  ```
- Check Slack channel for message

**Example Workflow Usage:**
```yaml
- name: Send Slack notification
  run: |
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"Main CI failed for commit '${{ github.sha }}'"}' \
      ${{ secrets.SLACK_WEBHOOK_URL }}
```

**Security Notes:**
- Webhook URLs act like passwords - treat as sensitive
- Can be revoked individually in Slack app settings
- Only send non-sensitive information (commit SHA, branch, status)
- Never include personal data or API credentials in messages
- Rotate annually as security best practice

### 7. CLAUDE_CODE_OAUTH_TOKEN (REQUIRED)

Authentication token for Claude Code integration with GitHub workflows for AI-assisted tasks.

**Where It's Used:**
- Claude interactive workflow: AI-powered issue/PR assistance on `@claude` mentions
- Claude code-review workflow: Automated code review on PR creation

**Setup Steps:**

1. Access Claude Code:
   - Visit [code.claude.com](https://code.claude.com)
   - Log in with your Anthropic account (create if needed)

2. Generate OAuth Token:
   - Navigate to settings or token generation page
   - Follow Anthropic's current authentication flow
   - Generate a new authentication token
   - Copy the token (displayed only once)

3. Add to GitHub Secrets:
   - Go to repository `Settings` → `Secrets and variables` → `Actions`
   - Click `New repository secret`
   - Name: `CLAUDE_CODE_OAUTH_TOKEN`
   - Value: Your Claude Code OAuth Token

4. Click `Add secret`

**Verification:**
- Create a test issue or comment on PR with `@claude`
- Verify Claude workflow executes and responds

**Current Usage:**
```yaml
- name: Run Claude Code
  uses: anthropics/claude-code-action@v1
  with:
    claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

**Security Notes:**
- Treat as sensitive as database passwords
- Never commit or expose in logs
- Rotate every 180 days
- Monitor token usage for unusual activity
- Can be revoked and regenerated independently

**How to Rotate:**
1. Generate new token in Claude Code settings
2. Update secret in GitHub Actions
3. Verify workflows complete successfully
4. Revoke old token in Claude Code

## Workflow Dependencies Matrix

This table shows which secrets are required for each workflow:

| Workflow | TEST_DB_PASSWORD | CODECOV_TOKEN | GITHUB_TOKEN | DOCKER_* | SLACK_* | CLAUDE_TOKEN |
|----------|------------------|---------------|--------------|----------|---------|--------------|
| pr-ci.yaml | REQUIRED | OPTIONAL | REQUIRED | - | - | - |
| main-ci.yaml | REQUIRED | OPTIONAL | REQUIRED | - | OPTIONAL | - |
| deploy.yaml | REQUIRED | - | - | REQUIRED | - | - |
| benchmarks.yaml | REQUIRED | - | REQUIRED | - | - | - |
| monthly-regression.yaml | - | - | REQUIRED | - | OPTIONAL | - |
| claude.yml | - | - | - | - | - | REQUIRED |
| claude-code-review.yml | - | - | - | - | - | REQUIRED |

**Legend:**
- REQUIRED: Workflow will fail if secret is not configured
- OPTIONAL: Workflow will skip step or continue with warning
- `-`: Secret not used in this workflow

## Security Best Practices

### General Guidelines

1. **Principle of Least Privilege**
   - Create separate credentials for each service and environment
   - Use scoped tokens (e.g., Docker Hub PATs) instead of master passwords
   - Limit token permissions to minimum required

2. **Rotation Schedule**
   - REQUIRED secrets: 90 days
   - Database passwords: 90 days
   - Access tokens: 180 days
   - Webhook URLs: 365 days (as needed)
   - Compromise detection: Immediate

3. **Secret Storage**
   - Never store secrets in `.env` files committed to Git
   - Never print secrets in workflow logs
   - Use `echo "::add-mask::${{ secrets.SECRET }}"` to mask sensitive output
   - Keep written records in secure vault only

4. **Monitoring & Auditing**
   - Audit GitHub Actions secret usage regularly
   - Monitor failed authentication attempts
   - Check Docker Hub for unauthorized image access
   - Review Slack webhook message history

5. **Compromise Response**
   - Immediately revoke compromised credential
   - Generate new credential
   - Update in GitHub Secrets
   - Review recent workflow runs for unauthorized access
   - Notify team of compromise

### Per-Secret Guidelines

#### Database Credentials
- Use dedicated test account (not production DB access)
- Restrict network access to CI runners only
- Monitor failed connection attempts
- Log all database operations during CI runs

#### API Tokens (Codecov, Docker Hub, Claude)
- Use personal access tokens, never account passwords
- Enable token expiration where available
- Monitor token activity for unusual patterns
- Revoke individually upon compromise

#### Webhooks (Slack)
- Verify webhook recipient channel is appropriate for messages
- Audit who can post to that channel
- Monitor webhook delivery success/failures
- Revoke compromised webhooks immediately

## Rotation Procedures

### Monthly Rotation (90-day secrets)

**Test Database Password:**
1. Set reminder for 90-day rotation
2. Generate new password: `openssl rand -base64 16`
3. Update GitHub secret
4. Monitor next workflow run for authentication success
5. Document rotation in changelog
6. If using locally, update `.env` file

### Quarterly Rotation (180-day secrets)

**Codecov Token, Docker Hub PAT, Claude Code Token:**
1. Generate new token in respective service
2. Test new token locally if possible
3. Update GitHub secret with new value
4. Verify next workflow using that secret succeeds
5. Revoke old token in service (can't be done until verified)
6. Document rotation

### Annual Review (365-day secrets)

**Slack Webhook URL:**
1. Verify webhook still active and delivering messages
2. Review recent webhook messages for security/appropriateness
3. Check Slack app for unauthorized access
4. Generate new webhook if rotation policy requires
5. Document review

## Troubleshooting

### Workflow Fails with "Secret not found"
- Verify secret is spelled exactly as referenced in workflow (case-sensitive)
- Check secret is added to correct repository (not organization level only)
- Confirm workflow file was edited after secret was added

### "Unauthorized" Errors
- Verify secret value is current (may have expired or been rotated elsewhere)
- Check service credentials haven't been revoked
- Test credential manually outside of GitHub (if possible)
- Regenerate token and update secret

### Workflow Shows Empty Secret in Logs
- This is expected - GitHub automatically masks secret values
- If you see `${{ secrets.SECRET_NAME }}`, secret retrieval failed
- Verify workflow permissions include `secrets: read`

### Coverage Upload Fails
- Codecov service may be temporarily down
- Try re-running workflow (coverage upload has `continue-on-error: true`)
- Check Codecov status page: [codecov.io/status](https://codecov.io/status)
- CODECOV_TOKEN might be revoked or expired

### Docker Push Fails
- Verify DOCKER_USERNAME and DOCKER_PASSWORD are both configured
- Check Docker Hub account permissions for target repositories
- Verify Docker Hub hasn't rate-limited your IP (temporary)
- Ensure personal access token hasn't expired

## Related Documentation

- GitHub Actions Security: https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions
- GitHub Encrypted Secrets: https://docs.github.com/en/actions/security-guides/encrypted-secrets
- CI/CD Workflows: `docs/architecture/cicd-workflows.md`
- Project Setup: `CLAUDE.md`

## Support

For issues with GitHub Secrets or CI/CD workflows:

1. Check `docs/architecture/cicd-workflows.md` for workflow-specific details
2. Review workflow logs in GitHub Actions for error messages
3. Consult this guide's troubleshooting section
4. Open GitHub issue for persistent problems

---

**Last Updated:** 2026-02-03
**Version:** 1.0
**Maintained By:** DevOps Team
