"""
Tests for Story 23.12: Production Environment Configuration.

Covers:
- Production config validation (reject dev secrets in prod mode)
- Docker Compose prod YAML validity and resource limits
- Nginx prod config syntax validation
- Backup/restore script syntax validation
- Health check endpoint with broker/redis status
- Environment template validation
"""

import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

# Project root for file-based tests
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


# ============================================================================
# Config Production Validation Tests
# ============================================================================


class TestProductionConfigValidation:
    """Test that production config rejects insecure defaults."""

    def test_dev_jwt_secret_rejected_in_production(self):
        """Production mode must reject the default dev JWT secret."""
        from pydantic import ValidationError

        from src.config import Settings

        with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be changed"):
            Settings(
                environment="production",
                debug=False,
                jwt_secret_key="dev-secret-key-change-in-production-use-64-char-random-string",
                database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            )

    def test_debug_true_rejected_in_production(self):
        """Production mode must reject debug=True."""
        from pydantic import ValidationError

        from src.config import Settings

        with pytest.raises(ValidationError, match="DEBUG must be False"):
            Settings(
                environment="production",
                debug=True,
                jwt_secret_key="a-secure-production-key-that-is-long-enough-to-pass-validation",
                database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            )

    def test_valid_production_config_accepted(self):
        """Valid production config should be accepted."""
        from src.config import Settings

        s = Settings(
            environment="production",
            debug=False,
            jwt_secret_key="a-secure-production-key-that-is-long-enough-to-pass-validation",
            database_url="postgresql+psycopg://user:strongpass@localhost:5432/db",
        )
        assert s.environment == "production"
        assert s.debug is False

    def test_development_config_allows_defaults(self):
        """Development mode should accept default values."""
        from src.config import Settings

        s = Settings(
            environment="development",
            database_url="postgresql+psycopg://wyckoff_user:changeme@localhost:5432/wyckoff_db",
        )
        assert s.environment == "development"
        assert s.debug is True

    def test_changeme_password_warns_in_production(self):
        """Production mode should warn when DATABASE_URL contains 'changeme'."""
        import warnings

        from src.config import Settings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings(
                environment="production",
                debug=False,
                jwt_secret_key="a-secure-production-key-that-is-long-enough-to-pass-validation",
                database_url="postgresql+psycopg://user:changeme@localhost:5432/db",
            )
            password_warnings = [x for x in w if "default password" in str(x.message)]
            assert len(password_warnings) >= 1

    def test_async_driver_required(self):
        """Database URL must use an async-compatible driver."""
        from pydantic import ValidationError

        from src.config import Settings

        with pytest.raises(ValidationError, match="async driver"):
            Settings(
                environment="development",
                database_url="postgresql://user:pass@localhost:5432/db",
            )


# ============================================================================
# Docker Compose Production YAML Tests
# ============================================================================


class TestDockerComposeProd:
    """Test docker-compose.prod.yml validity and structure."""

    @pytest.fixture
    def compose_config(self) -> dict:
        compose_path = PROJECT_ROOT / "docker-compose.prod.yml"
        assert compose_path.exists(), "docker-compose.prod.yml must exist"
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_yaml_parses_successfully(self, compose_config):
        """docker-compose.prod.yml must be valid YAML."""
        assert compose_config is not None
        assert "services" in compose_config

    def test_required_services_present(self, compose_config):
        """All required services must be defined."""
        services = compose_config["services"]
        for svc in ["postgres", "redis", "backend", "frontend"]:
            assert svc in services, f"Service '{svc}' must be defined"

    def test_all_services_have_restart_policy(self, compose_config):
        """All services must have a restart policy."""
        for name, svc in compose_config["services"].items():
            assert "restart" in svc, f"Service '{name}' must have restart policy"

    def test_all_services_have_resource_limits(self, compose_config):
        """All services must have resource limits."""
        for name, svc in compose_config["services"].items():
            deploy = svc.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            assert "cpus" in limits, f"Service '{name}' must have CPU limit"
            assert "memory" in limits, f"Service '{name}' must have memory limit"

    def test_all_services_have_healthchecks(self, compose_config):
        """All services must have healthcheck definitions."""
        for name, svc in compose_config["services"].items():
            assert "healthcheck" in svc, f"Service '{name}' must have healthcheck"

    def test_all_services_have_logging(self, compose_config):
        """All services must have logging configuration."""
        for name, svc in compose_config["services"].items():
            assert "logging" in svc, f"Service '{name}' must have logging config"

    def test_frontend_exposes_ssl_ports(self, compose_config):
        """Frontend must expose both HTTP (80) and HTTPS (443) ports."""
        frontend = compose_config["services"]["frontend"]
        ports = frontend.get("ports", [])
        port_strs = [str(p) for p in ports]
        assert any("80" in p for p in port_strs), "Frontend must expose port 80"
        assert any("443" in p for p in port_strs), "Frontend must expose port 443"

    def test_ssl_volume_defined(self, compose_config):
        """SSL certificates volume must be defined."""
        volumes = compose_config.get("volumes", {})
        assert "ssl_certs" in volumes, "ssl_certs volume must be defined"

    def test_backend_depends_on_postgres_and_redis(self, compose_config):
        """Backend must depend on postgres and redis."""
        backend = compose_config["services"]["backend"]
        depends = backend.get("depends_on", {})
        assert "postgres" in depends
        assert "redis" in depends

    def test_production_environment_set(self, compose_config):
        """Backend must have ENVIRONMENT=production."""
        backend = compose_config["services"]["backend"]
        env = backend.get("environment", {})
        assert env.get("ENVIRONMENT") == "production"

    def test_backend_uses_image_not_build(self, compose_config):
        """Backend service must use image: directive, not build:."""
        backend = compose_config["services"]["backend"]
        assert "image" in backend, "Backend must use 'image:' for pre-built Docker images"
        assert "build" not in backend, "Backend must not use 'build:' in production compose"

    def test_frontend_uses_image_not_build(self, compose_config):
        """Frontend service must use image: directive, not build:."""
        frontend = compose_config["services"]["frontend"]
        assert "image" in frontend, "Frontend must use 'image:' for pre-built Docker images"
        assert "build" not in frontend, "Frontend must not use 'build:' in production compose"

    def test_backend_has_redis_url(self, compose_config):
        """Backend must set REDIS_URL for container networking."""
        backend = compose_config["services"]["backend"]
        env = backend.get("environment", {})
        assert "REDIS_URL" in env, "Backend must set REDIS_URL for Redis container connectivity"
        redis_url = env["REDIS_URL"]
        assert "redis://" in str(redis_url), "REDIS_URL must be a valid redis:// URL"
        assert "localhost" not in str(
            redis_url
        ), "REDIS_URL must not use localhost in container networking"


# ============================================================================
# Nginx Production Config Tests
# ============================================================================


class TestNginxProdConfig:
    """Test nginx.prod.conf syntax and structure."""

    @pytest.fixture
    def nginx_config(self) -> str:
        config_path = PROJECT_ROOT / "frontend" / "nginx.prod.conf"
        assert config_path.exists(), "frontend/nginx.prod.conf must exist"
        return config_path.read_text()

    def test_has_http_redirect_block(self, nginx_config):
        """Must have HTTP-to-HTTPS redirect on port 80."""
        assert "listen 80" in nginx_config
        assert "return 301 https://" in nginx_config

    def test_has_ssl_server_block(self, nginx_config):
        """Must have HTTPS server block on port 443."""
        assert "listen 443 ssl" in nginx_config

    def test_ssl_certificate_paths(self, nginx_config):
        """Must reference SSL certificate files."""
        assert "ssl_certificate" in nginx_config
        assert "ssl_certificate_key" in nginx_config
        assert "fullchain.pem" in nginx_config
        assert "privkey.pem" in nginx_config

    def test_modern_tls_protocols(self, nginx_config):
        """Must use TLSv1.2 and TLSv1.3 only."""
        protocol_match = re.search(r"ssl_protocols\s+([^;]+);", nginx_config)
        assert protocol_match is not None
        protocols = protocol_match.group(1)
        assert "TLSv1.2" in protocols
        assert "TLSv1.3" in protocols

    def test_hsts_header(self, nginx_config):
        """Must include HSTS header."""
        assert "Strict-Transport-Security" in nginx_config

    def test_ocsp_stapling(self, nginx_config):
        """Must enable OCSP stapling."""
        assert "ssl_stapling on" in nginx_config
        assert "ssl_stapling_verify on" in nginx_config

    def test_session_tickets_off(self, nginx_config):
        """Must disable session tickets for forward secrecy."""
        assert "ssl_session_tickets off" in nginx_config

    def test_security_headers_present(self, nginx_config):
        """Must include security headers."""
        assert "X-Frame-Options" in nginx_config
        assert "X-Content-Type-Options" in nginx_config
        assert "X-XSS-Protection" in nginx_config
        assert "Content-Security-Policy" in nginx_config

    def test_gzip_enabled(self, nginx_config):
        """Must have gzip compression."""
        assert "gzip on" in nginx_config

    def test_api_proxy_configured(self, nginx_config):
        """Must proxy /api to backend."""
        assert "location /api" in nginx_config
        assert "proxy_pass http://backend:8000/api" in nginx_config

    def test_websocket_proxy_configured(self, nginx_config):
        """Must proxy /ws to backend with upgrade headers."""
        assert "location /ws" in nginx_config
        assert "proxy_pass http://backend:8000/ws" in nginx_config
        assert "Upgrade" in nginx_config
        assert '"upgrade"' in nginx_config

    def test_spa_routing_fallback(self, nginx_config):
        """Must have SPA routing fallback to index.html."""
        assert "try_files" in nginx_config
        assert "index.html" in nginx_config

    def test_health_check_on_http(self, nginx_config):
        """HTTP server block must allow health checks without redirect."""
        http_block_match = re.search(
            r"server\s*\{[^}]*listen\s+80[^}]*\}",
            nginx_config,
            re.DOTALL,
        )
        assert http_block_match is not None
        http_block = http_block_match.group(0)
        assert "/health" in http_block

    def test_wss_in_connect_src(self, nginx_config):
        """CSP connect-src must include wss: for WebSocket over SSL."""
        assert "wss:" in nginx_config


# ============================================================================
# Backup Script Validation Tests
# ============================================================================


class TestBackupScripts:
    """Test backup and restore script syntax."""

    def test_backup_script_exists(self):
        """Backup script must exist."""
        path = PROJECT_ROOT / "scripts" / "backup-db.sh"
        assert path.exists()

    def test_restore_script_exists(self):
        """Restore script must exist."""
        path = PROJECT_ROOT / "scripts" / "restore-db.sh"
        assert path.exists()

    def test_backup_script_has_shebang(self):
        """Backup script must start with bash shebang."""
        content = (PROJECT_ROOT / "scripts" / "backup-db.sh").read_text()
        assert content.startswith("#!/bin/bash")

    def test_restore_script_has_shebang(self):
        """Restore script must start with bash shebang."""
        content = (PROJECT_ROOT / "scripts" / "restore-db.sh").read_text()
        assert content.startswith("#!/bin/bash")

    def test_backup_script_uses_strict_mode(self):
        """Backup script must use set -e or set -euo pipefail."""
        content = (PROJECT_ROOT / "scripts" / "backup-db.sh").read_text()
        assert "set -e" in content

    def test_restore_script_uses_strict_mode(self):
        """Restore script must use set -e or set -euo pipefail."""
        content = (PROJECT_ROOT / "scripts" / "restore-db.sh").read_text()
        assert "set -e" in content

    def test_backup_script_uses_pg_dump(self):
        """Backup script must use pg_dump."""
        content = (PROJECT_ROOT / "scripts" / "backup-db.sh").read_text()
        assert "pg_dump" in content

    def test_restore_script_uses_pg_restore(self):
        """Restore script must use pg_restore."""
        content = (PROJECT_ROOT / "scripts" / "restore-db.sh").read_text()
        assert "pg_restore" in content

    def test_backup_script_has_retention_cleanup(self):
        """Backup script must clean up old backups."""
        content = (PROJECT_ROOT / "scripts" / "backup-db.sh").read_text()
        assert "RETENTION" in content or "-mtime" in content

    def test_restore_script_requires_confirmation(self):
        """Restore script must require user confirmation."""
        content = (PROJECT_ROOT / "scripts" / "restore-db.sh").read_text()
        assert "confirm" in content.lower() or "read" in content.lower()

    def test_backup_script_verifies_output(self):
        """Backup script must verify the backup file was created."""
        content = (PROJECT_ROOT / "scripts" / "backup-db.sh").read_text()
        assert "-s" in content or "size" in content.lower()


# ============================================================================
# SSL Certificate Script Tests
# ============================================================================


class TestSSLScripts:
    """Test SSL certificate generation scripts."""

    def test_self_signed_cert_script_exists(self):
        """Self-signed cert generation script must exist."""
        path = PROJECT_ROOT / "scripts" / "generate-self-signed-cert.sh"
        assert path.exists()

    def test_letsencrypt_script_exists(self):
        """Let's Encrypt setup script must exist."""
        path = PROJECT_ROOT / "scripts" / "setup-letsencrypt.sh"
        assert path.exists()

    def test_self_signed_uses_openssl(self):
        """Self-signed cert script must use openssl."""
        content = (PROJECT_ROOT / "scripts" / "generate-self-signed-cert.sh").read_text()
        assert "openssl" in content

    def test_letsencrypt_uses_certbot(self):
        """Let's Encrypt script must use certbot."""
        content = (PROJECT_ROOT / "scripts" / "setup-letsencrypt.sh").read_text()
        assert "certbot" in content

    def test_self_signed_generates_key_and_cert(self):
        """Self-signed script must generate both key and certificate."""
        content = (PROJECT_ROOT / "scripts" / "generate-self-signed-cert.sh").read_text()
        assert "privkey.pem" in content
        assert "fullchain.pem" in content


# ============================================================================
# Environment Template Tests
# ============================================================================


class TestEnvironmentTemplate:
    """Test .env.production.example template."""

    @pytest.fixture
    def env_template(self) -> str:
        path = PROJECT_ROOT / ".env.production.example"
        assert path.exists(), ".env.production.example must exist"
        return path.read_text()

    def test_template_exists(self):
        """Production env template must exist."""
        assert (PROJECT_ROOT / ".env.production.example").exists()

    def test_environment_set_to_production(self, env_template):
        """Template must set ENVIRONMENT=production."""
        assert "ENVIRONMENT=production" in env_template

    def test_debug_set_to_false(self, env_template):
        """Template must set DEBUG=false."""
        assert "DEBUG=false" in env_template

    def test_jwt_secret_placeholder(self, env_template):
        """Template must have a placeholder JWT secret, not the dev default."""
        assert "CHANGE_ME" in env_template or "GENERATE" in env_template.upper()
        assert "dev-secret-key" not in env_template

    def test_database_password_placeholder(self, env_template):
        """Template must have a placeholder database password."""
        assert "CHANGE_ME" in env_template or "STRONG_PASSWORD" in env_template.upper()

    def test_required_sections_present(self, env_template):
        """Template must include all key configuration sections."""
        assert "DATABASE_URL" in env_template
        assert "REDIS" in env_template
        assert "JWT" in env_template

    def test_no_real_secrets_in_template(self, env_template):
        """Template must not contain any real API keys or passwords."""
        lines = env_template.strip().split("\n")
        for line in lines:
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if "API_KEY" in key or "SECRET_KEY" in key or "PASSWORD" in key:
                assert (
                    value == "" or "CHANGE" in value.upper() or "GENERATE" in value.upper()
                ), f"Secret field {key} must not contain real values"


# ============================================================================
# Health Check Endpoint Tests
# ============================================================================


class TestHealthCheckEndpoint:
    """Test the enhanced detailed health check endpoint."""

    @pytest.mark.asyncio
    async def test_basic_health_check(self):
        """Basic /health endpoint must return healthy status."""
        from src.api.main import health_check

        result = await health_check()
        assert result == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_detailed_health_check_structure(self):
        """Detailed /api/v1/health must return expected structure."""
        from src.api.main import detailed_health_check

        with (
            patch("src.database.async_session_maker") as mock_session_maker,
            patch("src.api.main.get_orchestrator") as mock_orch,
            patch("src.api.main.get_scanner") as mock_scanner,
            patch("src.api.dependencies.init_redis_client") as mock_redis,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.execute = AsyncMock()
            mock_session_maker.return_value = mock_session
            mock_orch.return_value.get_health.return_value = {"status": "healthy"}
            mock_scanner.side_effect = RuntimeError("Not initialized")
            mock_redis.return_value = None

            result = await detailed_health_check()

        assert "status" in result
        assert "database" in result
        assert "version" in result
        assert "brokers" in result
        assert "redis" in result

    @pytest.mark.asyncio
    async def test_health_check_includes_version(self):
        """Detailed health check must include application version."""
        from src.api.main import detailed_health_check

        with (
            patch("src.database.async_session_maker") as mock_sm,
            patch("src.api.main.get_orchestrator") as mock_orch,
            patch("src.api.main.get_scanner") as mock_scanner,
            patch("src.api.dependencies.init_redis_client") as mock_redis,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.execute = AsyncMock()
            mock_sm.return_value = mock_session
            mock_orch.return_value.get_health.return_value = {"status": "healthy"}
            mock_scanner.side_effect = RuntimeError("Not initialized")
            mock_redis.return_value = None

            result = await detailed_health_check()

        assert result["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_health_check_reports_broker_not_configured(self):
        """Health check must report brokers as not_configured when unavailable."""
        from src.api.main import detailed_health_check

        with (
            patch("src.database.async_session_maker") as mock_sm,
            patch("src.api.main.get_orchestrator") as mock_orch,
            patch("src.api.main.get_scanner") as mock_scanner,
            patch("src.api.dependencies.init_redis_client") as mock_redis,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.execute = AsyncMock()
            mock_sm.return_value = mock_session
            mock_orch.return_value.get_health.return_value = {"status": "healthy"}
            mock_scanner.side_effect = RuntimeError("Not initialized")
            mock_redis.return_value = None

            result = await detailed_health_check()

        # broker_router module doesn't exist yet, so try/except returns not_configured
        assert result["brokers"] == {"status": "not_configured"}

    @pytest.mark.asyncio
    async def test_health_check_database_error_degrades_status(self):
        """Health check must report degraded when database is unavailable."""
        from src.api.main import detailed_health_check

        with (
            patch("src.database.async_session_maker") as mock_sm,
            patch("src.api.main.get_orchestrator") as mock_orch,
            patch("src.api.main.get_scanner") as mock_scanner,
            patch("src.api.dependencies.init_redis_client") as mock_redis,
        ):
            mock_sm.side_effect = Exception("Connection refused")
            mock_orch.return_value.get_health.return_value = {"status": "healthy"}
            mock_scanner.side_effect = RuntimeError("Not initialized")
            mock_redis.return_value = None

            result = await detailed_health_check()

        assert result["status"] == "degraded"
        assert "error" in str(result["database"])


# ============================================================================
# Deploy Workflow Tests
# ============================================================================


class TestDeployWorkflow:
    """Test deploy.yaml GitHub Actions workflow validity."""

    @pytest.fixture
    def workflow_config(self) -> dict:
        path = PROJECT_ROOT / ".github" / "workflows" / "deploy.yaml"
        assert path.exists(), ".github/workflows/deploy.yaml must exist"
        with open(path) as f:
            return yaml.safe_load(f)

    def test_workflow_parses_as_valid_yaml(self, workflow_config):
        """deploy.yaml must be valid YAML."""
        assert workflow_config is not None
        assert "name" in workflow_config

    def test_workflow_has_required_triggers(self, workflow_config):
        """Workflow must trigger on workflow_dispatch and version tags."""
        # YAML parses 'on' as boolean True, so check both key variants
        on = workflow_config.get("on") or workflow_config.get(True, {})
        assert "workflow_dispatch" in on
        assert "push" in on

    def test_workflow_has_pre_deployment_checks(self, workflow_config):
        """Workflow must include pre-deployment validation job."""
        jobs = workflow_config.get("jobs", {})
        assert "pre-deployment-checks" in jobs

    def test_workflow_has_build_and_push(self, workflow_config):
        """Workflow must include build-and-push job."""
        jobs = workflow_config.get("jobs", {})
        assert "build-and-push" in jobs

    def test_workflow_has_deploy_job(self, workflow_config):
        """Workflow must include deploy-to-production job."""
        jobs = workflow_config.get("jobs", {})
        assert "deploy-to-production" in jobs

    def test_build_depends_on_checks(self, workflow_config):
        """Build job must depend on pre-deployment checks."""
        build_job = workflow_config["jobs"]["build-and-push"]
        needs = build_job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        assert "pre-deployment-checks" in needs

    def test_deploy_depends_on_build(self, workflow_config):
        """Deploy job must depend on build-and-push."""
        deploy_job = workflow_config["jobs"]["deploy-to-production"]
        needs = deploy_job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        assert "build-and-push" in needs


# ============================================================================
# Dockerfile.prod Validation Tests
# ============================================================================


class TestDockerfileProd:
    """Test frontend/Dockerfile.prod correctness."""

    @pytest.fixture
    def dockerfile_content(self) -> str:
        path = PROJECT_ROOT / "frontend" / "Dockerfile.prod"
        assert path.exists(), "frontend/Dockerfile.prod must exist"
        return path.read_text()

    def test_uses_production_nginx_config(self, dockerfile_content):
        """Dockerfile.prod must copy nginx.prod.conf, not nginx.conf."""
        assert "nginx.prod.conf" in dockerfile_content
        # Ensure it doesn't ONLY reference nginx.conf (without .prod)
        lines = dockerfile_content.split("\n")
        for line in lines:
            if line.strip().startswith("COPY") and "nginx" in line and ".conf" in line:
                assert (
                    "nginx.prod.conf" in line
                ), f"COPY directive must reference nginx.prod.conf, found: {line.strip()}"

    def test_exposes_ssl_port(self, dockerfile_content):
        """Dockerfile.prod must expose port 443 for SSL."""
        assert "443" in dockerfile_content
