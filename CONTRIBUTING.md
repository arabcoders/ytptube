# Contributing to YTPTube

YTPTube is my own little pet project that was based on [meTube](https://github.com/alexta69/metube). I have specific 
requirements and preferences for how this project is developed and maintained. Discuss your change and get approval 
before starting work or opening a pull request. Unsolicited pull requests will be closed without review.

## Before You Start

Report vulnerabilities privately through [SECURITY.md](SECURITY.md). For bugs, proposed changes or general questions,
open a GitHub issue. Explain what you want to change, why, your proposed approach and which existing behavior or use
cases it affects.

Bug fixes, functional improvements and measurable performance work take priority. An interface change needs more than
personal preference. I will decline a proposal or ask for a different scope or approach.

## Development

Branch from `dev`:

```bash
git checkout dev
git pull origin dev
git switch -C feature/descriptive-name
```

Run the backend from the repository root:

```bash
uv run python -m app.main --dev
```

Add `--no-auto-migration` to prevent automatic upgrades of initialized databases. Startup requires their revision to
match the latest shipped migration. Fresh databases are still initialized. This flag also works without `--dev`.

Run the frontend from `ui/`:

```bash
bun run dev
```

Install the repository's pre-commit hook:

```bash
./.githooks/install
```

Use `./.githooks/install --force` to replace an existing pre-commit hook.

Add executable local checks to one of these directories:

* `.git/hooks/pre-commit.d/` for all changes
* `.git/hooks/pre-commit.d/backend/` for backend changes
* `.git/hooks/pre-commit.d/frontend/` for frontend changes

Keep each change focused and follow the patterns already used in the codebase. New features require tests. Bug fixes
require a regression test that fails before the fix and passes after it. Update documentation when behavior, setup, or
an API changes.

Run the checks that apply to the files you changed.

Backend checks:

```bash
uv run ruff format --check app/
uv run ruff check app/
uv run ty check app/
uv run pytest app/ -q
```

Frontend checks, run from `ui/`:

```bash
bun run format:check
bun run lint:ci
bun run typecheck
bun run test:ci
```

## AI-Assisted Work

AI-assisted tools are allowed in this project. Disclosure is not required. The standard for a contribution does not
change based on which tools were used to produce it.

You must understand every submitted change, check it against the existing code, test it, and explain its behavior and
design decisions. Generated code, tests, or documentation that has not received meaningful human review will be
rejected. Tests must validate behavior rather than exist only to increase coverage.

## Pull Requests

Every pull request must target `dev`, never `master`. Reference the approved issue and describe what changed and why. 
Include any breaking changes or migration steps, and make sure the applicable checks pass.

Use this checklist before submitting:

- [ ] The change was discussed and approved before implementation
- [ ] The pull request targets `dev`
- [ ] Relevant tests were added or updated and pass
- [ ] Applicable formatting, linting, and type checks pass
- [ ] Documentation was updated where needed

A pull request will be closed without review if it:

* Was opened without prior discussion and approval
* Targets `master` instead of `dev`
* Includes an unapproved large refactor or architectural change
* Does not fit the approved scope or project goals
* Contains work the contributor cannot explain or justify
* Purely AI-generated dump with no human understanding, review, or testing.

## Questions

Check existing GitHub issues. For short questions, join the project [Discord server](https://discord.gg/G3GpVR8xpb). 
YTPTube is maintained as a solo project, so replies may take some time.

## License

By contributing, you agree that your contribution will be licensed under the project's MIT License.
