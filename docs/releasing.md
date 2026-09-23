# Releasing

RPM and DEB packages are the primary distribution formats. COPR, a Launchpad
PPA, and GitHub Release assets are the primary channels. PyPI is secondary and
uses the `monitorcontrol-linux` distribution name; the import package,
executable, RPM, and DEB remain `monitorcontrol`.

## One-time external configuration

The GitHub `release` environment is already configured with required owner
approval, administrator bypass disabled, and a deployment branch/tag policy
restricted to `v*` tags. Keep those protections in place.

Configure these environment variables on `release`:

- `COPR_PROJECT`: the `owner/project` accepted by `copr-cli build`.
- `PPA_TARGET`: the `ppa:owner/archive` accepted by `dput`.

Configure these environment secrets:

- `COPR_CONFIG`: the complete COPR API configuration file. The workflow writes
  it to `~/.config/copr` with mode 0600.
- `PPA_GPG_PRIVATE_KEY`: ASCII-armored private key registered with Launchpad.
- `PPA_GPG_PASSPHRASE`: passphrase for that key.
- `PPA_GPG_FINGERPRINT`: full fingerprint of that key.

Create the COPR project and enable Fedora 43 and Fedora 44 chroots. The workflow
submits exactly one Fedora 44 SRPM and waits for COPR; it never submits a local
binary RPM. Create the Launchpad PPA, register the public signing key, and make
sure `dput` may upload to `PPA_TARGET`. Launchpad receives only the signed noble
source package with version `X.Y.Z-1ppa1~noble1`.

On PyPI, create a Trusted Publisher for:

- PyPI project: `monitorcontrol-linux`
- Owner: `jaimehisao`
- Repository: `monitorcontrol`
- Workflow: `release.yml`
- Environment: `release`

No PyPI token is used or supported.

The publication credentials are currently absent: `COPR_CONFIG`,
`PPA_GPG_PRIVATE_KEY`, `PPA_GPG_PASSPHRASE`, and `PPA_GPG_FINGERPRINT` are not
provided by this repository or change. The COPR/PPA/PyPI publisher projects
also have not been verified by this code change. Publishing cannot succeed
until the external projects, variables, secrets, and PyPI Trusted Publisher
are configured.

## Prepare and tag

Prepare a release branch with:

```bash
python3 scripts/release.py prepare X.Y.Z
python3 scripts/release.py check
```

Replace generated changelog placeholders, merge the reviewed commit to `main`,
then create and push an annotated signed tag on that exact commit:

```bash
git switch main
git pull --ff-only origin main
git tag -s vX.Y.Z -m "MonitorControl vX.Y.Z"
git tag -v vX.Y.Z
git push origin vX.Y.Z
```

The workflow requires exact `vX.Y.Z`, matching version surfaces, an annotated
tag whose GitHub API `verification.verified` value is true, and a tag commit
that is an ancestor of `origin/main`. Lightweight and unsigned tags fail
clearly.

Run `workflow_dispatch` before tagging to build and validate every artifact.
Dispatch runs never publish.

## Draft-first publication and recovery

A tag run builds Python distributions and canonical source, Fedora 43/44 RPMs
and SRPMs, Debian 13 binary/source packages, and an unsigned Ubuntu 24.04 noble
source package. It validates a closed artifact inventory, generates SPDX JSON,
checksums the public assets, and records GitHub build provenance.

The protected publication job first creates (or reuses) a draft GitHub Release.
It then signs the noble source, uploads all GitHub assets, publishes
`monitorcontrol-linux` to PyPI using Trusted Publishing, submits the SRPM to
COPR, and uploads the signed source to Launchpad. A separate protected final job
polls all three public repositories and only then marks the GitHub Release
non-draft and latest.

If publication or verification fails, the GitHub Release stays draft. Correct
the external configuration or wait for repository metadata, then rerun only
failed jobs when GitHub permits it. The upload step uses `--clobber`, and public
repository uploads are immutable, so never delete and reuse a version.

Released versions are immutable. Any correction after an upload must be a new
patch release with a new `X.Y.Z` and tag; do not move, recreate, or force-push a
release tag.
