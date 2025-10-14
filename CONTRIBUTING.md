# Contributing to YTPTube

Thank you for your interest in contributing to **YTPTube**! We welcome contributions from the community to help improve this project.

This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Contributing to YTPTube](#contributing-to-ytptube)
  - [Table of Contents](#table-of-contents)
  - [Code of Conduct](#code-of-conduct)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
      - [Backend Requirements](#backend-requirements)
      - [Frontend Requirements](#frontend-requirements)
      - [Optional Tools](#optional-tools)
    - [Installing Required Package Managers](#installing-required-package-managers)
      - [Installing uv (Python Package Manager)](#installing-uv-python-package-manager)
      - [Installing pnpm (Node.js Package Manager)](#installing-pnpm-nodejs-package-manager)
    - [Cloning the Repository](#cloning-the-repository)
  - [Development Setup](#development-setup)
    - [Backend Setup (Python)](#backend-setup-python)
    - [Frontend Setup (Node.js)](#frontend-setup-nodejs)
  - [Development Workflow](#development-workflow)
    - [Working on a Feature or Bug Fix](#working-on-a-feature-or-bug-fix)
  - [Branching Strategy](#branching-strategy)
    - [Important Rules:](#important-rules)
    - [Branch Naming Conventions:](#branch-naming-conventions)
  - [Testing Requirements](#testing-requirements)
    - [Backend Testing (Python)](#backend-testing-python)
    - [Frontend Testing (TypeScript/Vue)](#frontend-testing-typescriptvue)
    - [Test Coverage Expectations](#test-coverage-expectations)
  - [Code Quality and Linting](#code-quality-and-linting)
    - [Backend (Python)](#backend-python)
    - [Frontend (TypeScript/Vue)](#frontend-typescriptvue)
    - [Code Quality Checklist](#code-quality-checklist)
  - [Pre-commit Hooks](#pre-commit-hooks)
    - [Setting Up Pre-commit Hooks](#setting-up-pre-commit-hooks)
    - [Before Submitting](#before-submitting)
  - [Pull Request Guidelines](#pull-request-guidelines)
    - [Creating a Pull Request](#creating-a-pull-request)
    - [PR Review Process](#pr-review-process)
    - [After Your PR is Merged](#after-your-pr-is-merged)
  - [Code Style](#code-style)
    - [Python Code Style](#python-code-style)
    - [TypeScript/Vue Code Style](#typescriptvue-code-style)
  - [Getting Help](#getting-help)
    - [Resources](#resources)
    - [Ask Questions](#ask-questions)
    - [Reporting Bugs](#reporting-bugs)
  - [License](#license)

---

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive community.

---

## Getting Started

### Prerequisites

Before you begin, ensure you have the following tools installed on your system:

#### Backend Requirements

- **Python 3.13+**: YTPTube requires Python 3.13 or higher
- **uv**: Modern Python package manager and virtual environment tool

#### Frontend Requirements

- **Node.js 18+**: Required for the Nuxt/Vue frontend
- **pnpm**: Fast, disk space efficient package manager

#### Optional Tools

- **Git**: Version control
- **Docker**: For containerized development (optional)
- **ffmpeg**: Required for video player functionality

### Installing Required Package Managers

#### Installing uv (Python Package Manager)

**uv** is a fast Python package installer and resolver written in Rust. It's used for managing Python dependencies and virtual environments.

**On Linux/macOS:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**On Windows (PowerShell):**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Using pip:**

```bash
pip install uv
```

**Verify installation:**

```bash
uv --version
```

For more information, visit: https://github.com/astral-sh/uv

#### Installing pnpm (Node.js Package Manager)

**pnpm** is a fast, disk space efficient package manager for Node.js.

**Using npm:**

```bash
npm install -g pnpm
```

**Using Homebrew (macOS):**

```bash
brew install pnpm
```

**Using Scoop (Windows):**

```bash
scoop install pnpm
```

**Using standalone script:**

```bash
curl -fsSL https://get.pnpm.io/install.sh | sh -
```

**Verify installation:**

```bash
pnpm --version
```

For more information, visit: https://pnpm.io/installation

### Cloning the Repository

Clone the repository to your local machine:

```bash
git clone https://github.com/arabcoders/ytptube.git
cd ytptube
```

**Important**: Always work on the `dev` branch, not `master`/`main`:

```bash
git checkout dev
```

---

## Development Setup

### Backend Setup (Python)

1. **Navigate to the project root:**

```bash
cd ytptube
```

2. **Install Python dependencies using uv:**

```bash
uv sync
```

This will:
- Create a virtual environment (`.venv/`)
- Install all dependencies from `pyproject.toml`
- Install development dependencies

3. **Install development dependencies:**

Development dependencies are defined in `pyproject.toml` under `[dependency-groups]`:

```bash
uv sync --group dev
```

4. **Verify installation:**

```bash
uv run python --version
uv run pytest --version
```

5. **Run the backend development server:**

```bash
uv run app/main.py
```

The backend API will be available at `http://localhost:8081`

### Frontend Setup (Node.js)

1. **Navigate to the UI directory:**

```bash
cd ui
```

2. **Install Node.js dependencies using pnpm:**

```bash
pnpm install
```

3. **Run the frontend development server:**

```bash
pnpm dev
```

The frontend will be available at `http://localhost:3000` (or the port shown in the terminal)

4. **Verify the setup:**

```bash
pnpm run typecheck
pnpm run lint
```

---

## Development Workflow

### Working on a Feature or Bug Fix

1. **Ensure you're on the `dev` branch:**

```bash
git checkout dev
git pull origin dev
```

2. **Create a feature branch:**

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

3. **Make your changes**

4. **Test your changes** (see [Testing Requirements](#testing-requirements))

5. **Run code quality checks** (see [Code Quality and Linting](#code-quality-and-linting))

6. **Commit your changes:**

```bash
git add .
git commit -m "feat: add new feature description"
# or
git commit -m "fix: fix bug description"
```

7. **Push to your fork:**

```bash
git push origin feature/your-feature-name
```

8. **Create a Pull Request** targeting the `dev` branch

---

## Branching Strategy

**YTPTube uses a two-branch strategy:**

- **`master`**: Production-ready code. Only maintainers merge to this branch.
- **`dev`**: Development branch. **All contributions must target this branch.**

### Important Rules:

- ✅ **DO**: Create feature branches from `dev`
- ✅ **DO**: Submit pull requests to `dev`
- ❌ **DON'T**: Submit pull requests to `master`/`main`
- ❌ **DON'T**: Commit directly to `dev` (use feature branches)

### Branch Naming Conventions:

- `feature/description` - For new features
- `fix/description` - For bug fixes
- `refactor/description` - For code refactoring
- `docs/description` - For documentation updates
- `test/description` - For test additions/improvements

---

## Testing Requirements

**All code changes must include appropriate tests.** This ensures code quality and prevents regressions.

### Backend Testing (Python)

Tests are located in `app/tests/` and use **pytest**.

**Running tests:**

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest app/tests/test_download.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=app --cov-report=html
```

**Creating new tests:**

1. Create a test file in `app/tests/` with the prefix `test_`
2. Use pytest conventions:

```python
import pytest
from app.library.YourModule import YourClass

class TestYourClass:
    def test_feature_name(self):
        """Test description."""
        # Arrange
        instance = YourClass()
        
        # Act
        result = instance.method()
        
        # Assert
        assert result == expected_value
    
    @pytest.mark.asyncio
    async def test_async_feature(self):
        """Test async functionality."""
        result = await async_function()
        assert result is not None
```

**Testing Singleton Classes:**

When testing singleton classes, always reset the singleton instance:

```python
from app.library.Presets import Presets

class TestPresets:
    def setup_method(self):
        """Reset singleton before each test."""
        Presets._reset_singleton()
    
    def teardown_method(self):
        """Reset singleton after each test."""
        Presets._reset_singleton()
```

### Frontend Testing (TypeScript/Vue)

Tests are located in `ui/tests/` and use **Vitest**.

**Running tests:**

```bash
cd ui

# Run all tests
pnpm test

# Run in watch mode
pnpm test:watch

# Run with coverage
pnpm run test --coverage
```

**Creating new tests:**

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import YourComponent from '~/components/YourComponent.vue'

describe('YourComponent', () => {
    it('renders correctly', () => {
        const wrapper = mount(YourComponent)
        expect(wrapper.exists()).toBe(true)
    })
    
    it('handles user interaction', async () => {
        const wrapper = mount(YourComponent)
        await wrapper.find('button').trigger('click')
        expect(wrapper.emitted('event-name')).toBeTruthy()
    })
})
```

### Test Coverage Expectations

- **New features**: Must include comprehensive tests
- **Bug fixes**: Must include a test that reproduces the bug
- **Refactoring**: Existing tests should still pass
- **Coverage goal**: Aim for >80% code coverage on new code

---

## Code Quality and Linting

### Backend (Python)

YTPTube uses **Ruff** for linting and formatting Python code.

**Running Ruff:**

```bash
# Check for linting issues
uv run ruff check app/

# Auto-fix linting issues
uv run ruff check --fix app/

# Format code
uv run ruff format app/

# Check specific file
uv run ruff check app/library/Download.py
uv run ruff check --fix app/library/Download.py
```

**Configuration:**

Ruff configuration is in `pyproject.toml` under `[tool.ruff]`.

### Frontend (TypeScript/Vue)

The frontend uses **ESLint** for linting and **TypeScript** for type checking.

**Running checks:**

```bash
cd ui

# Type checking
pnpm run typecheck

# Linting
pnpm run lint

# Auto-fix linting issues
pnpm run lint:fix
```

### Code Quality Checklist

Before committing, ensure:

- ✅ All tests pass (`uv run pytest` and `pnpm test`)
- ✅ No linting errors (`ruff check` and `pnpm run lint`)
- ✅ TypeScript compilation succeeds (`pnpm run typecheck`)
- ✅ Code is formatted properly
- ✅ No unused imports or variables
- ✅ Type hints are present (Python 3.13+)

---

## Pre-commit Hooks

YTPTube uses a custom shell script-based pre-commit hook that runs all checks in parallel for faster execution.

### Setting Up Pre-commit Hooks

1. **Create the pre-commit hook script:**

Create a file at `.git/hooks/pre-commit` with the following content:

```bash
#!/bin/sh
set -eu

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT" || exit 1

PIDS_FILE=$(mktemp)
trap 'rm -f "$PIDS_FILE"' EXIT

export CI=1
run_step() {
  local label="$1"
  shift
  echo "🔹 Starting $label..." >&2
  (
    if ! "$@"; then
      echo "❌ [$label] failed. Commit aborted." >&2
      exit 1
    else
      echo "✅ [$label] passed." >&2
    fi
  ) &
  echo $! >>"$PIDS_FILE"
}

run_step "Ruff (Python linter)" uv run ruff check app/
run_step "PyTest" uv run pytest app/ -q
run_step "ESLint" pnpm --dir ./ui run lint
run_step "Vitest" pnpm --dir ./ui run test

fail=0
while read -r pid; do
  if ! wait "$pid"; then
    fail=1
  fi
done <"$PIDS_FILE"

if [ "$fail" -eq 1 ]; then
  echo "❌ One or more checks failed. Commit aborted." >&2
  exit 1
fi

echo "✅ All checks passed. Commit allowed."
exit 0
```

2. **Make the hook executable:**

```bash
chmod +x .git/hooks/pre-commit
```

3. **Test the hook:**

```bash
# Test manually
.git/hooks/pre-commit

# Or make a test commit
git commit --allow-empty -m "test: verify pre-commit hook"
```

---

### Before Submitting

✅ **Checklist:**

- [ ] Code is on a feature branch created from `dev`
- [ ] All tests pass locally
- [ ] Code passes linting and formatting checks
- [ ] TypeScript types are properly defined (no `any`) without justification
- [ ] New features include tests
- [ ] Documentation is updated (if applicable)
- [ ] Commit messages are clear and descriptive
- [ ] Pre-commit hooks pass

---

## Pull Request Guidelines

### Creating a Pull Request

1. **Push your branch to GitHub:**

```bash
git push origin feature/your-feature-name
```

2. **Open a Pull Request on GitHub**

3. **Target the `dev` branch** (not `master`)

4. **Fill out the PR template** with:
   - Description of changes
   - Related issue numbers (if applicable)
   - Testing performed
   - Screenshots (for UI changes)
   - Breaking changes (if any)

### PR Review Process

1. **Automated Checks**: CI pipeline runs tests and linting
2. **Code Review**: Maintainers review your code
3. **Feedback**: Address any requested changes
4. **Approval**: Once approved, maintainers will merge

### After Your PR is Merged

1. **Delete your feature branch** (optional but recommended)
2. **Pull the latest `dev` branch:**

```bash
git checkout dev
git pull origin dev
```

3. **Celebrate!** Thank you for contributing!

---

## Code Style

### Python Code Style

- **Line length**: 120 characters
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings
- **Type hints**: Use Python 3.13+ type hints
- **Imports**: Absolute imports from `app.library`
- **Comparison**: Use Yoda comparisons for literals (`"value" == variable`)

**Example:**

```python
from app.library.Download import Download
from app.library.ItemDTO import ItemDTO

async def process_download(item: ItemDTO) -> bool:
    """Process a download item."""
    try:
        if "pending" == item.status:  # Yoda comparison
            result = await Download.start(item)
            return result.success
    except Exception as e:
        LOG.error(f"Download failed: {e}")
        return False
```

### TypeScript/Vue Code Style

- **Type safety**: No `any` types without justification
- **Explicit imports**: Import all Vue functions explicitly
- **Component structure**: Use `<script setup lang="ts">`
- **Props/Emits**: Always type-define

**Example:**

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { DownloadItem } from '~/types/download'

const props = defineProps<{
    items: Array<DownloadItem>
}>()

const emit = defineEmits<{
    (e: 'itemSelected', item: DownloadItem): void
}>()

const selectedItem = ref<DownloadItem | null>(null)
</script>
```

---

## Getting Help

### Resources

- **API Docs**: See [API.md](API.md) for API reference
- **FAQ**: Check [FAQ.md](FAQ.md) for common questions
- **Issues**: Browse existing [GitHub Issues](https://github.com/arabcoders/ytptube/issues)

### Ask Questions

- **GitHub Discussions**: For general questions and discussions
- **GitHub Issues**: For bug reports and feature requests
- **Pull Requests**: For code review and implementation questions
- **Discord**: Join our community on Discord (link in README)

### Reporting Bugs

When reporting bugs, please include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Detailed steps to reproduce the bug
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Environment**: OS, Python version, Node version, etc.
6. **Logs**: Relevant error messages or logs
7. **Screenshots**: If applicable

---

## License

By contributing to YTPTube, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

Thank you for contributing to YTPTube! Your efforts help make this project better for everyone.
