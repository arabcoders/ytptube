# Contributing to YTPTube

YTPTube is a personal-first project maintained according to the maintainer's needs and preferences. Contributions are
welcome after discussion and approval, but the maintainer decides the project's direction and which changes are
accepted.

Do not start work or open a pull request without approval. Unsolicited pull requests will be closed without review.

## Before You Start

Open a GitHub issue for a bug fix or small feature. Use a GitHub discussion for a larger change or a general question.
Your proposal should explain:

* What you want to change
* Why the change is needed
* How you plan to implement it
* Which use cases or existing behavior are relevant

Bug fixes, functional improvements, and measurable performance work take priority. A personal preference or a claim
that something looks better is not enough reason to change the interface. Large refactors, new abstractions, and
architectural changes need approval before implementation.

Wait for an explicit response from the maintainer before writing code. Approval may include limits or a requested
approach. A proposal can be declined if it does not fit the project's goals or the maintainer's use cases.

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

Run the frontend from `ui/`:

```bash
bun run dev
```

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

Every pull request must target `dev`, never `master`. Reference the approved issue or discussion and describe what
changed and why. Include any breaking changes or migration steps, and make sure the applicable checks pass.

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

Check existing GitHub issues and discussions first. For short questions, join the project
[Discord server](https://discord.gg/G3GpVR8xpb). YTPTube is maintained as a solo project, so replies may take some time.

## License

By contributing, you agree that your contribution will be licensed under the project's MIT License.
