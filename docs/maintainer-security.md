# Maintainer security

Complete this checklist when the public GitHub repository is created. It is
separate from the integration's runtime security and protects the source,
releases and people who report vulnerabilities.

## Owner account

- Enable two-factor authentication and store the recovery codes somewhere
  other than the computer used to publish releases.
- Review active sessions, authorized applications and SSH keys periodically.
- Remember that the email address attached to a Git commit becomes public. Use
  GitHub's private `noreply` commit address if that is preferable.
- Never store a Solesta password, session cookie, Home Assistant backup,
  diagnostic download or archive in the repository or a public issue.

## Repository settings

- Keep the default GitHub Actions token at read-only permissions. Grant write
  permission to an individual workflow only if a future task actually needs it.
- In the repository's Actions settings, require actions to be pinned to a
  full-length commit SHA. The included workflows already meet this requirement.
- Enable Dependabot alerts and security updates, secret scanning and push
  protection where GitHub offers them for the repository.
- Enable private vulnerability reporting before referring reporters to the
  repository's **Security** tab.
- After the workflows have run once, add a ruleset for the `main` branch.
  Require a pull request and the Ruff, Python, JavaScript, HACS, Hassfest and
  both CodeQL checks before merge; block force pushes and deletion of the
  branch.
- Protect release tags matching `v*` from modification or deletion.

The workflows in this repository use fixed commit hashes for third-party
actions, disabled checkout credentials and job time limits. Jobs have read-only
repository access; only CodeQL additionally receives the `security-events:
write` permission needed to publish its findings. Dependabot is configured to
propose action and test-dependency updates. Review those pull requests and merge
them only after all checks pass.

## Release handling

- Create releases from a clean checkout of the protected default branch.
- Check the staged files for secrets and local data before every push and
  release.
- Use semantic version tags such as `v0.2.3`; do not move an existing release
  tag to different code.
- Treat unexpected workflow or dependency changes as security-sensitive during
  review.

## Publish the 1.0.0 candidate without private project history

The development branch contains original installation evidence in earlier
commits. Pseudonymizing the latest reports does not remove those originals
from that branch's history. Do not push or merge that branch for publication.

Use a new release branch based on the verified public `main` commit, apply
only the inspected candidate files, and make a new commit there. Do not merge
the private development branch or include its `.git`, work directories,
backups, evidence archive or pseudonym map. This keeps the existing public
history and adds the reviewed candidate as a new change; it requires no
force-push or rewriting of public commits.

Before pushing, inspect the exact tree and all commits reachable from the
release branch. Recheck if public `main` has moved. Run local checks on that
tree, then run the GitHub HACS/Hassfest, tests and CodeQL jobs on the published
release branch/PR. HACS validates a GitHub ref; a local structural check is not
an executed HACS Action. Publish the release only after the required results
have passed and the release decision is explicit.

The [M7 preparation report](results/solesta-m7-release-preparation-2026-11-05.md)
records the verified base, candidate checks and remaining gates. Private
original evidence stays outside the publication payload.
