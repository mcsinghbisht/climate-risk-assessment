# Git Setup Guide for Climate Risk Assessment

Complete guide to initialize and configure a git repository for this project.

---

## Quick Start (TL;DR)

```bash
cd Climate_Risk_Assessment

# Initialize git repo
git init

# Configure git (first time only)
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Climate Risk Assessment system (35 tasks complete)"

# (Optional) Connect to GitHub
git branch -M main
git remote add origin https://github.com/yourusername/climate-risk-assessment.git
git push -u origin main
```

---

## Detailed Setup Steps

### Step 1: Initialize the Repository

```bash
cd Climate_Risk_Assessment
git init
```

**What it does:**
- Creates a `.git` folder (hidden on Unix/Linux/Mac)
- Initializes git tracking for this directory and all subdirectories

**Verify:**
```bash
git status
# Should show: On branch master (or main), nothing to commit
```

---

### Step 2: Configure Git (First Time Only)

Set your name and email. This information will be attached to every commit:

**Global Configuration (all projects on this machine):**
```bash
git config --global user.name "Your Full Name"
git config --global user.email "your.email@example.com"
```

**Project-Only Configuration (this project only):**
```bash
git config user.name "Your Full Name"
git config user.email "your.email@example.com"
```

**Verify configuration:**
```bash
git config --list
# Look for user.name and user.email
```

---

### Step 3: Review .gitignore

A `.gitignore` file has already been created for you. It excludes:
- Virtual environments (`venv/`)
- Python cache files (`__pycache__/`, `*.pyc`)
- Environment files (`.env`)
- IDE files (`.vscode/`, `.idea/`)
- Generated databases and caches (`*.db`, `data/.cache/`)
- Temporary files (`temp/`, `tmp/`)

**Verify .gitignore is in place:**
```bash
cat .gitignore
# Should show the exclusion patterns
```

---

### Step 4: Add Files to Staging

**Add all files (recommended for initial commit):**
```bash
git add .
```

**Review what will be committed:**
```bash
git status
# Shows all staged files in green
```

**Selectively add files (if needed):**
```bash
git add src/              # Add just the src folder
git add CLAUDE.md         # Add specific file
git add docs/             # Add just docs
```

---

### Step 5: Create Initial Commit

```bash
git commit -m "Initial commit: Climate Risk Assessment system (35 tasks complete)

- Backend: Data ingestion, risk scoring, monitoring, alerts, portfolio aggregation
- Frontend: Streamlit dashboard with Portfolio Manager and Underwriter roles
- LLM Layer: Claude-powered Q&A with 8 curated tools
- Testing: Unit tests for chat agent
- Documentation: Comprehensive guides and API reference

See CLAUDE.md for project overview and docs/INDEX.md for documentation hub."
```

**Multi-line commits (recommended for initial commit):**
- First line: Short summary (< 72 chars)
- Blank line
- Detailed description (can span multiple lines)
- Reference to documentation

**Verify:**
```bash
git log
# Shows your initial commit with author, date, and message
```

---

### Step 6 (Optional): Connect to GitHub

#### Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `climate-risk-assessment`
3. Description: "AI-powered geospatial risk monitoring agent for insurance"
4. Choose: **Private** (recommended for insurance/proprietary data) or **Public**
5. Click "Create repository"

#### Connect Local Repo to GitHub

```bash
# If starting with default branch name
git branch -M main

# Add remote (replace <username> with your GitHub username)
git remote add origin https://github.com/<username>/climate-risk-assessment.git

# Verify remote is set
git remote -v
# Should show:
# origin  https://github.com/<username>/climate-risk-assessment.git (fetch)
# origin  https://github.com/<username>/climate-risk-assessment.git (push)

# Push to GitHub
git push -u origin main
```

**Using SSH (if you prefer):**
```bash
git remote add origin git@github.com:<username>/climate-risk-assessment.git
git push -u origin main
```

---

## After Initial Setup

### Regular Workflow

```bash
# Make changes to files...

# Check what changed
git status

# Stage changes
git add src/my_changes.py docs/UPDATES.md

# Commit with a message
git commit -m "Fix: cache invalidation logic for property updates

- Prevents stale explanations when risk scores change
- Adds property_id index to cache lookup
- Refs: src/llm/cache.py"

# Push to GitHub (if connected)
git push
```

### Useful Commands

**View commit history:**
```bash
git log                          # Full history
git log --oneline               # Condensed view
git log --oneline -10           # Last 10 commits
git log --graph --oneline --all # Visual branch graph
```

**Check branch status:**
```bash
git status                       # Current branch and uncommitted changes
git branch                       # List local branches
git branch -a                    # List all branches (local + remote)
```

**Compare changes:**
```bash
git diff                         # Unstaged changes
git diff --staged               # Staged changes
git diff HEAD~1                 # Last commit vs current
```

**Undo changes:**
```bash
git restore <file>              # Discard changes in file
git restore --staged <file>     # Unstage file
git reset --soft HEAD~1         # Undo last commit (keep changes staged)
git reset --hard HEAD~1         # Undo last commit (discard changes)
```

---

## Branching Strategy (Recommended)

For ongoing development, use a simple branching model:

### Main Branch
```bash
# main = production-ready code
# Keep main stable, never force-push
```

### Feature Branches
```bash
# For new features or fixes
git checkout -b feature/add-export-functionality
# Make changes, commit
git commit -m "Feature: Add PDF export for portfolio reports"

# Push to GitHub
git push -u origin feature/add-export-functionality

# Create Pull Request on GitHub (optional but recommended)
# - Allows code review
# - Verifies tests pass
# - Merge via PR interface
```

### Naming Convention
- `feature/` — New features
- `fix/` — Bug fixes
- `docs/` — Documentation updates
- `refactor/` — Code refactoring
- `test/` — Test additions
- `perf/` — Performance improvements

---

## .gitignore Details

**What's excluded:**
- `venv/` — Virtual environment (never commit)
- `__pycache__/` — Python cache files (auto-generated)
- `.env` — Environment variables with secrets (never commit)
- `.vscode/` — IDE settings (optional per-machine)
- `*.db` — SQLite databases (can be large, regenerable)
- `data/.cache/` — LLM explanation cache (regenerable)
- `*.log` — Log files (regenerable)

**What's included:**
- `src/` — All source code
- `tests/` — All test files
- `docs/` — All documentation
- `config/` — Configuration templates (but not .env)
- `requirements*.txt` — Dependency lists
- `.gitignore` — This file itself

**Override .gitignore (if needed):**
```bash
# Force add ignored file
git add -f data/important_file.db

# Remove file from tracking (keep it locally)
git rm --cached .env
```

---

## Authentication & Security

### SSH Setup (Recommended)

SSH is more secure than HTTPS:

```bash
# Generate SSH key (Windows/Mac/Linux)
ssh-keygen -t ed25519 -C "your.email@example.com"

# Add to ssh-agent
ssh-add ~/.ssh/id_ed25519

# Add public key to GitHub
# 1. Copy: cat ~/.ssh/id_ed25519.pub
# 2. Go to GitHub Settings → SSH and GPG keys
# 3. Click "New SSH key" and paste

# Test connection
ssh -T git@github.com
# Should say: Hi <username>! You've successfully authenticated...
```

### HTTPS with Personal Access Token (Alternative)

```bash
# Create PAT on GitHub: Settings → Developer settings → Personal access tokens
# Copy token and use as password when pushing

# Store credentials (avoid re-entering token)
git config --global credential.helper store
# Next push will prompt once, then cache credentials
```

### Never Commit Secrets

Even though `.gitignore` excludes `.env`, be extra careful:

```bash
# ✅ Good: Store secrets in .env (not tracked)
# .env
ANTHROPIC_API_KEY=sk-...

# ❌ Bad: Never commit secrets in code
# Never put keys in Python files or config/
```

---

## Troubleshooting

### "fatal: not a git repository"
```bash
# You're not in the project directory
cd Climate_Risk_Assessment
git status
```

### "Please tell me who you are"
```bash
# Configure git user
git config user.name "Your Name"
git config user.email "your@email.com"
```

### Accidentally Committed .env
```bash
# Remove from git history
git rm --cached .env
echo ".env" >> .gitignore
git commit -m "Remove .env from tracking"

# (Optional) Remove from GitHub history
# (requires force-push, only do on unpushed commits)
git reset --soft HEAD~1
```

### Large Files Slow Down Push
```bash
# Check file sizes
git ls-files -l | sort -k4 -r | head -10

# If you committed large files:
git rm --cached *.db
echo "*.db" >> .gitignore
git commit -m "Remove large database files from tracking"
```

### Accidentally Deleted Files
```bash
# Restore deleted file
git restore <filename>

# Restore all deleted files
git restore .
```

---

## Next Steps

1. **Verify setup:**
   ```bash
   git log                    # Should show initial commit
   git remote -v              # Should show GitHub remote (if connected)
   ```

2. **Share repository:**
   - Give GitHub URL to team members
   - For private repos: Add collaborators on GitHub

3. **Set up branch protection (on GitHub):**
   - Go to Settings → Branches
   - Add rule for "main" branch
   - Require pull request reviews before merge
   - Require status checks to pass

4. **Configure CI/CD (optional):**
   - GitHub Actions can run tests automatically
   - See `docs/operations-guide.md` for test commands

5. **Monitor repository:**
   - Regular backups (GitHub provides redundancy)
   - Review commit history regularly
   - Keep dependencies up to date

---

## Reference

**Git Documentation:**
- https://git-scm.com/doc
- https://github.com/git-tips/tips

**GitHub Guides:**
- https://guides.github.com/
- https://github.com/features/actions (CI/CD)

**Best Practices:**
- https://www.atlassian.com/git/tutorials/saving-changes/gitignore
- https://www.conventionalcommits.org/ (commit message format)
