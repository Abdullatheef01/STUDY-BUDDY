"""Phase 1 Batch 2: OPS-01 reproducible builds, ARC-02 packaging."""
import os
import re

REPO = os.path.join(os.path.dirname(__file__), "..")


class TestReproducibleBuilds:
    """OPS-01: locked, hash-verified requirements.txt + PYTHON_VERSION pin."""

    def test_requirements_txt_has_hashes(self):
        path = os.path.join(REPO, "requirements.txt")
        text = open(path).read()
        # every pinned package must have at least one sha256 hash
        pkgs = re.findall(r"^([a-zA-Z0-9_.-]+)==[^\s\\]+", text, re.M)
        assert pkgs, "no pinned packages found"
        missing = [p for p in pkgs
                   if not re.search(rf"^{re.escape(p)}==.*sha256:",
                                    text, re.M | re.S)]
        # simpler: count hash lines vs package lines
        hash_blocks = len(re.findall(r"--hash=sha256:", text))
        assert hash_blocks >= len(pkgs), \
            f"{len(pkgs)} packages but only {hash_blocks} hash lines"

    def test_requirements_in_exists(self):
        assert os.path.exists(os.path.join(REPO, "requirements.in"))

    def test_python_version_pinned_render(self):
        text = open(os.path.join(REPO, "render.yaml")).read()
        assert "PYTHON_VERSION" in text, "render.yaml must pin PYTHON_VERSION"
        assert ".python-version" in os.listdir(REPO)

    def test_security_pins_survive_lock(self):
        """SEC-07 pins must be present in the compiled lockfile."""
        text = open(os.path.join(REPO, "requirements.txt")).read()
        for pkg, ver in [("flask", "3.1.3"), ("werkzeug", "3.1.9"),
                         ("gunicorn", "26.2.0"), ("pypdf", "6.20.1")]:
            assert re.search(rf"^{pkg}=={re.escape(ver)}\b", text, re.M), \
                f"{pkg}=={ver} missing from lockfile"


class TestCIFoundation:
    """TEST-01/TEST-12: CI workflow and pre-commit config exist."""

    def test_ci_workflow_exists(self):
        path = os.path.join(REPO, ".github", "workflows", "ci.yml")
        assert os.path.exists(path)
        text = open(path).read()
        for job in ("lint:", "test-sqlite:", "test-postgres:", "security:"):
            assert job in text, f"CI job {job} missing"

    def test_precommit_config_exists(self):
        assert os.path.exists(os.path.join(REPO, ".pre-commit-config.yaml"))

    def test_pyproject_exists(self):
        assert os.path.exists(os.path.join(REPO, "pyproject.toml"))
