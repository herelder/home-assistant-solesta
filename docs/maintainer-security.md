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
