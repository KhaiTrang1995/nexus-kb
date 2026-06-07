# Deploy Skill

## Trigger Context
This skill activates automatically when the task involves:
- Deploying to staging or production
- CI/CD pipeline configuration
- Docker / container builds
- Cloud provider (AWS, GCP, Azure) operations

## Workflow

### Pre-deploy Checklist
1. All tests passing: `npm test`
2. No lint errors: `npm run lint`
3. Environment variables set for target environment
4. Database migrations reviewed

### Deploy Steps
```bash
# Build production artifact
npm run build

# Run deploy script (see deploy-config.md for environment vars)
./scripts/deploy.sh --env production
```

### Post-deploy Verification
- Check service health endpoint: `GET /api/health`
- Review application logs for errors
- Smoke test critical user flows

## Rollback
```bash
./scripts/deploy.sh --rollback --env production
```

## References
- Environment-specific config: `.claude/skills/deploy/deploy-config.md`
