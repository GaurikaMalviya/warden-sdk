# Warden Engineering Rules

## Project

Warden is a Python SDK providing a runtime guardrail layer for autonomous AI agents.

The product is infrastructure/SDK-first, not dashboard-first.

## Mandatory Engineering Workflow

For every stage:

1. Inspect the existing repository before changing anything.
2. Create or update the specification before implementation.
3. Create a small implementation plan.
4. Implement incrementally.
5. Test with pytest.
6. Review the implementation.
7. Simplify only when behavior remains unchanged.
8. Do not proceed to the next stage without verification.

## Agent Skills

Use the relevant installed Agent Skills for every stage.

Preferred lifecycle:

- Specification:
  /agent-skills:spec-driven-development

- Planning:
  /agent-skills:planning-and-task-breakdown

- Implementation:
  /agent-skills:incremental-implementation
  /agent-skills:test-driven-development

- Testing:
  /agent-skills:test-driven-development

- Review:
  /agent-skills:code-review-and-quality

- Simplification:
  /agent-skills:code-simplification

For security-sensitive work also use:
  /agent-skills:security-and-hardening

For performance-sensitive work also use:
  /agent-skills:performance-optimization

Do not skip applicable skills.

## Ponytail Principles

Apply Ponytail principles to every implementation:

- Inspect before creating.
- Reuse existing code first.
- Prefer standard library functionality.
- Reuse installed dependencies.
- Avoid unnecessary abstractions.
- Avoid speculative architecture.
- Avoid unnecessary files.
- Avoid unnecessary dependencies.
- Avoid duplicate functionality.
- Do not rewrite working code without a requirement.
- Implement the smallest production-quality solution satisfying the current specification.

Ponytail must never override:
- correctness
- security
- testability
- explicit requirements
- maintainability

Do not sacrifice safety or correctness merely to reduce code.

## Stage Isolation

Only implement the current stage.

Do NOT:
- implement future stages early
- create future agents early
- create a dashboard unless explicitly requested
- add infrastructure not required by the current stage
- redesign the architecture without approval

## Human Checkpoints

After each stage:

1. Run tests.
2. Review changed files.
3. Review the diff.
4. Report assumptions.
5. Report dependencies added.
6. Report files changed.
7. Stop and wait for human approval.

Never automatically continue into the next stage.

## Security

Warden is security infrastructure.

Prefer fail-safe behavior where explicitly required by the specification.

Never hardcode API keys or secrets.

Never silently swallow security-relevant exceptions.

## Performance

The Interceptor is the critical low-latency path.

Do not introduce LLM calls into the deterministic Interceptor.

Measure performance instead of inventing latency numbers.

## Scope

Do not implement functionality that is not explicitly required by the current stage.