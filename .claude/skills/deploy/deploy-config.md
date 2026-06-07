# Deploy Configuration

## Environments

### Staging
| Variable | Value |
|---|---|
| `APP_ENV` | `staging` |
| `API_URL` | `https://api-staging.example.com` |
| `PORT` | `3000` |

### Production
| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `API_URL` | `https://api.example.com` |
| `PORT` | `8080` |

## Secrets Management
- Secrets are stored in the CI/CD vault (GitHub Actions Secrets / AWS Secrets Manager)
- Never commit `.env` files or raw credentials to git

## Docker
```dockerfile
# Build image
docker build -t myapp:latest .

# Run container
docker run -p 8080:8080 --env-file .env myapp:latest
```

## CI/CD Pipeline
- Provider: GitHub Actions
- Workflow file: `.github/workflows/deploy.yml`
- Branch rules:
  - `main` → auto-deploy to **staging**
  - `release/*` → manual approval → **production**
