# Contributing to YTPTube

YTPTube is a **personal-first project**. While contributions are welcome, **all final decisions rest with the maintainer**.

## Core Principles

* **The maintainer has final say** on all changes and project direction.
* This project is built **for personal use first**. Community contributions are secondary.
* **All contributions require prior discussion and approval.**
* **All pull requests must target the `dev` branch** never `master`.
* Contributions must align with the project's goals, architecture, and coding standards.

**Opening a PR without prior approval will result in immediate closure without review.**

---

## Contribution Process

### 1. Start a Discussion

Before writing any code, **propose your idea** through one of these channels:

* Open a **GitHub Issue** for bug fixes or small features
* Start a **GitHub Discussion** for larger changes or questions

**Include in your proposal:**
* **What** you want to change
* **Why** it's needed or beneficial
  * Bug fixes and functional improvements are prioritized
  * Performance enhancements with measurable impact
  * Features that align with the project's core purpose
  * **Not acceptable:** Personal UI/UX preferences, stylistic changes, or "I think it looks better" rationale
* **How** you plan to implement it (high-level approach)
* Any relevant context or use cases

### 2. Wait for Approval

* Only proceed after **explicit approval** from the maintainer to not waste effort.
* The maintainer may suggest modifications or alternative approaches.
* Not all proposals will be accepted this protects project coherence.

### 3. Develop Your Changes

**Branch from `dev`:**
```bash
git checkout dev
git pull origin dev
git checkout -b feature/descriptive-name
```

**Follow project standards:**
* Match existing code style and conventions
* Add or update tests for all changes:
  * New features **MUST** include tests
  * Bug fixes **MUST** include a regression test
* Ensure all linting and tests pass
* Keep changes focused and atomic

### 4. Submit a Pull Request

**Target the `dev` branch:**
* Reference the approved issue or discussion number
* Provide a clear description of what changed and why
* List any breaking changes or migration steps
* Ensure CI checks pass

**PR template checklist:**
- [ ] Discussed and approved beforehand
- [ ] Targets `dev` branch
- [ ] Tests added/updated and passing
- [ ] Linting passes
- [ ] Documentation updated (if needed)

---

## Automatic Rejections

The following will be **closed immediately without review**:

* PRs opened without prior discussion and approval
* PRs targeting `master` instead of `dev`
* Large refactors or architectural changes without approval
* Fully AI-generated code without meaningful human oversight
* Changes that don't align with project goals or philosophy
* PRs where the contributor cannot explain or justify the changes

---

## AI-Assisted Development

AI tools are **permitted** as development aids, but **you remain fully responsible** for all submitted code.

### Acceptable Use

AI-assisted code is welcome **when**:

* You **fully understand** every line being submitted
* The code **seamlessly integrates** with existing patterns and style
* You have **reviewed, tested, and validated** the output yourself
* **Comprehensive tests** are included (not AI-generated stubs)
* The code is **indistinguishable in quality** from hand-written contributions
* You can **explain and defend** design decisions in the PR

**AI is a tool, not a substitute for understanding.**

### Not Acceptable

The following will be rejected:

* Fully AI-generated PRs with minimal human review
* Code that introduces new patterns or abstractions without approval
* "Prompt-dump" output that doesn't match project conventions
* Changes the contributor cannot explain or justify
* AI-generated test suites that don't meaningfully validate behavior

### Disclosure

You are **not required** to disclose AI usage. However, if code quality suggests pure AI generation without human oversight, the PR will be closed.

**You are accountable for correctness, maintainability, and alignment regardless of how the code was created.**

---

## Testing Requirements

All contributions must include appropriate tests:

* **New features:** Full test coverage including edge cases
* **Bug fixes:** Regression test that fails before the fix and passes after
* **Refactors:** Existing tests must continue to pass
* **Performance changes:** Benchmarks or performance tests when applicable

Tests should be clear, maintainable, and actually validate the intended behavior.

---

## Questions?

* Check existing **Issues** and **Discussions** first
* Join the project **Discord** for real-time discussion
* Be patient, this is a personal project with limited maintenance time

---

## License

By contributing, you agree that your code will be licensed under the project's **MIT License**.

Thank you for respecting this contribution process. It helps maintain project quality and the maintainer's sanity.
