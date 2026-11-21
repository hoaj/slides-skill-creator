# How the Engine and Generator are released and installed

Research for [issue #8](https://github.com/hoaj/slides-skill-creator/issues/8), checked on 2026-11-21. Links to source code are pinned to the commit that was read.

## Recommendation

1. **Support Claude Code, Cursor and Copilot CLI in v0.1.0.** These are the three agents the precedent ships. Make Codex the first follow-up: it can already read a Claude manifest and the `hoaj/plugins` listing, but claiming support needs an end-to-end install test.
2. **Use one version for the Engine and Generator, tagged `vX.Y.Z`.** All three manifests carry it. A merge to `main` that raises it publishes the release. A pull request that changes shipped files must raise it, because some agents can deliver `main` whatever the version says.
3. **Generate release notes** from merged pull requests, with categories in `.github/release.yml`.
4. **Publish three assets:** `slides-engine-X.Y.Z.tar.gz`, `engine-manifest.json` and `SHA256SUMS`. Upgrade uses these and never GitHub's automatic source archives.
5. **Turn on immutable releases before v0.1.0 and add a build attestation.** Both are worth it. Immutability keeps every old release available as the merge base for Upgrade. The attestation proves that this repo's release workflow built the asset.
6. **List the plugin in `hoaj/plugins` without a `version` or `ref`:** a `url` source for Claude Code and a `github` source for Copilot CLI. Cursor uses the marketplace in this repo.

## 1. Manifests and marketplace entries

| | Claude Code | Cursor | Copilot CLI | Codex |
|---|---|---|---|---|
| **Plugin manifest** | `.claude-plugin/plugin.json`, optional ([docs][cc-manifest]) | `.cursor-plugin/plugin.json` ([docs][cursor-ref]) | First of `.plugin/`, root, `.github/plugin/`, `.claude-plugin/` ([docs][copilot-ref]) | Root `plugin.json`, or `.codex-plugin/plugin.json` as fallback ([docs][codex-build]); the code also accepts the [Claude and Cursor paths][codex-manifest-paths] |
| **Required manifest fields** | `name` ([docs][cc-manifest]) | `name` ([docs][cursor-ref]) | `name`; the Agent Plugins format also needs `$schema` ([docs][copilot-ref]) | No formal list; the minimal example has `$schema`, `name`, `version`, `description` ([docs][codex-build]) |
| **Marketplace file** | `.claude-plugin/marketplace.json` ([docs][cc-market]) | `.cursor-plugin/marketplace.json` ([docs][cursor-ref]) | First of root, `.plugin/`, `.github/plugin/`, `.claude-plugin/` ([docs][copilot-ref]) | `.agents/plugins/marketplace.json`, then `.claude-plugin/marketplace.json` ([code][codex-market-paths]) |
| **Required marketplace fields** | `name`, `owner`, `plugins` ([docs][cc-market]) | `name`, `owner`, `plugins` in the [docs][cursor-ref]; the [schema][cursor-schema] omits `owner` | `name`, `owner`, `plugins` ([docs][copilot-ref]) | `name`, `plugins` ([code][codex-raw-entry]) |
| **Required entry fields** | `name`, `source` ([docs][cc-market]) | `name` in the [docs][cursor-ref]; `name`, `source` in the [schema][cursor-schema] | `name`, `source` ([docs][copilot-ref]) | `name`, `source`. The [docs][codex-build] also ask for `policy`, but the [code][codex-raw-entry] defaults it |
| **Plugin from another repo?** | Yes: `github`, `url`, `git-subdir` ([docs][cc-market]) | **Unconfirmed**, see below | Yes: `github`, `url` ([docs][copilot-ref]) | Yes: `url`, `git-subdir` ([docs][codex-build]). A `github` source is [not in the parser][codex-source-enum] and is [skipped][codex-source-skip] |
| **Pin to a ref or commit** | `ref`, `sha` ([docs][cc-market]) | Not documented | `ref`, `sha` ([docs][copilot-ref]) | `ref`, `sha` ([code][codex-source-enum]) |

**Cursor and other repos.** The [`hoaj/plugins` README][plugins-cursor] says Cursor cannot list a plugin from another repo. Cursor's docs only describe a path or an object with `path`, but its [official schema][cursor-schema] describes `source` as a path "or a remote URL". All 155 entries in its [official marketplace][cursor-market] are local paths. A marketplace in this repo remains the safe choice, as already decided, but the reason should read "not confirmed" rather than "cannot".

**Source types differ.** The `hoaj/plugins` file for Claude Code is also the one Codex would read, so it must use `url`: Codex skips `github`. The `url` form also avoids the SSH-first clone that Claude Code [uses for `github` sources][cc-host], as the [`hoaj/plugins` README][plugins-listing-rule] already notes.

## 2. Cache and update

| | Where the copy lives | What triggers an update | Does the manifest version control it? |
|---|---|---|---|
| **Claude Code** | `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`; old versions are removed after 14 days ([docs][cc-loading]) | Manual by default. Auto-update is [off for third-party marketplaces][cc-loading] until a user or admin turns it on | **Yes.** The order is manifest, then marketplace entry, then commit SHA. If the computed version is unchanged, the cached copy stays ([docs][cc-loading]) |
| **Cursor** | Not documented | Team marketplaces re-index on push to the tracked branch, at most every 10 minutes ([docs][cursor-docs]). Updates for individual installs are not documented | **Not documented** |
| **Copilot CLI** | `~/.copilot/installed-plugins/<marketplace>/<plugin>`, with no version in the path ([docs][copilot-ref]) | `copilot plugin update`. A marketplace you added can opt in to session-start updates with `autoUpdate: true` ([docs][copilot-ref]) | **Not documented.** `/plugin` flags "a newer version" upstream, but the comparison is not described |
| **Codex** | `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/` ([docs][codex-build], [code][codex-plugin-root]) | Configured Git marketplaces [upgrade at startup][codex-auto-upgrade]. Listing plugins also starts a [background refresh][codex-list-refresh] | **Partly.** The background refresh [skips an unchanged version][codex-version-check], but a changed marketplace [forces a reinstall][codex-force-reinstall] whatever the version |

Two things follow:

- **A version bump is required.** Without one, Claude Code users never receive a change.
- **A version bump cannot hold work back.** With no `ref`, a fresh install takes the default branch, Codex can reinstall it at an unchanged version, and Cursor and Copilot CLI do not document a version gate. So `main` must always be releasable.

Always set `version`. Without one, Codex installs into a [`local` folder][codex-local-version], and [`local` outranks every numbered version][codex-active-version] if both are present.

## 3. Versions, tags and release notes

**One version line.** Separate Engine and Generator versions would need prefixed tags and a compatibility rule between them. With one line, a Generator-only release leaves the Engine's content hash unchanged, so Upgrade can report that there is nothing to do and open no pull request.

**Tag format `vX.Y.Z`.** Claude Code's `<plugin>--v<version>` tags and `claude plugin tag` exist so [other plugins can depend on version ranges][cc-deps]. A Slides skill holds a copy of the Engine instead of depending on the plugin, so that format adds nothing here.

**Release flow.** This follows the "merging a version bump publishes the release" pattern already [used in `hoaj/plugins`][plugins-release-rule]:

1. A pull request changes shipped files and raises `version` in all three manifests.
2. CI checks that the manifests agree, the version is above the latest tag, and `claude plugin validate --strict` [passes][cc-manifest]. The precedent's generator CI [does not check the version][scc-bump]. Cursor's own repo [fails CI when manifest versions differ][cursor-validate].
3. On merge, `release.yml` stops if the tag already exists. Otherwise it builds the assets and attests them with [`actions/attest`][gh-attest-howto], pinned to a commit SHA.
4. It runs `gh release create vX.Y.Z <assets> --target "$GITHUB_SHA" --generate-notes --notes-start-tag <previous-tag>`. With assets, this command [creates a draft, uploads, then publishes][gh-create], which is the order [GitHub recommends for immutable releases][gh-immutable].
5. It runs the verification commands from section 5 against the published release.

**Release notes.** [Generated notes][gh-notes] list merged pull requests and can be grouped by label in `.github/release.yml`. Use `breaking`, `engine`, `generator` and a `*` catch-all. Pass the previous tag explicitly, since the docs do not define the default. Notes [stay editable on an immutable release][gh-immutable], so Upgrade must not rely on them for anything it verifies.

## 4. What a release holds

| Asset | Contents |
|---|---|
| `slides-engine-X.Y.Z.tar.gz` | The Engine only, with its bundled third-party licences. Built reproducibly: sorted entries, fixed timestamps and owners |
| `engine-manifest.json` | Schema version, Engine version, source commit, a hash of the whole Engine tree, and each file's path, mode and SHA-256 |
| `SHA256SUMS` | Checksums of the two files above |

Do not use GitHub's source archives: their [compression can change over time][gh-archives], and `gh release verify-asset` [cannot verify them][gh-verify].

`engine.lock` in a Slides skill should record the version, commit, tarball SHA-256 and tree hash. Upgrade can then re-fetch the exact base release for its three-way merge and detect local edits to the Engine copy.

## 5. How Upgrade verifies a release

| Control | What it protects against | Cost | Verdict |
|---|---|---|---|
| `SHA256SUMS` | Corruption. Not tampering, since it comes from the same release | Trivial | Keep |
| [Immutable release][gh-immutable] | A moved tag or swapped asset. The tag name [cannot be reused][gh-immutable], and publishing creates a release attestation automatically | One repo setting. It [only applies to future releases][gh-immutable-enable], so enable it first. A bad release needs a new patch version | **Use** |
| [Artifact attestation][gh-attest-concept] | An asset that this repo's workflow did not build, such as one uploaded with a stolen token. It does [not prove the code is safe][gh-attest-concept] | One workflow step; [available in all public repos][gh-supply] | **Use** |

Upgrade runs these checks and stops on any failure:

```sh
gh release verify vX.Y.Z -R hoaj/slides-skill-creator
gh release verify-asset vX.Y.Z slides-engine-X.Y.Z.tar.gz -R hoaj/slides-skill-creator
gh release verify-asset vX.Y.Z engine-manifest.json -R hoaj/slides-skill-creator
gh release verify-asset vX.Y.Z SHA256SUMS -R hoaj/slides-skill-creator
gh attestation verify slides-engine-X.Y.Z.tar.gz \
  --repo hoaj/slides-skill-creator \
  --signer-workflow hoaj/slides-skill-creator/.github/workflows/release.yml
```

It then checks `SHA256SUMS` and every per-file hash, and extracts only regular files inside the expected folder.

These commands need [`gh` 2.81.0 or later][gh-281]. If `gh` is missing, Upgrade should stop by default. An explicit `--checksum-only` flag can fall back to the [SHA-256 `digest` in the releases API][gh-assets] and must report that it checked integrity only.

The two release commands were tried on GitHub's own immutable `cli/cli` v2.105.0 release, from outside a clone. The real asset passed, and a copy with one added byte failed with exit code 1.

## 6. Listing in `hoaj/plugins`

`.claude-plugin/marketplace.json`:

```json
{
  "name": "slides-skill-creator",
  "source": {
    "source": "url",
    "url": "https://github.com/hoaj/slides-skill-creator.git"
  },
  "description": "Create and maintain on-brand slide deck skills from a shared, versioned Engine.",
  "homepage": "https://github.com/hoaj/slides-skill-creator",
  "category": "development"
}
```

`.github/plugin/marketplace.json`:

```json
{
  "name": "slides-skill-creator",
  "source": { "source": "github", "repo": "hoaj/slides-skill-creator" },
  "description": "Create and maintain on-brand slide deck skills from a shared, versioned Engine."
}
```

- Add no entry to the Cursor file in `hoaj/plugins`. Extend its description and the README to send Cursor users to `hoaj/slides-skill-creator`.
- Do not set `version` in an entry. Claude Code [warns on a mismatch and uses `plugin.json`][cc-host].
- Do not set `ref`. Pinning would need a `hoaj/plugins` pull request for every release, and the Cursor marketplace has no documented equivalent.

In this repo, add `.cursor-plugin/marketplace.json` with one entry whose `source` is `"./"`, as [the precedent does][scc-cursor-market].

## 7. Compared with `site-cli-creator`

| | Precedent | This repo |
|---|---|---|
| Manifests | [Claude][scc-claude], [Cursor][scc-cursor], [Copilot][scc-copilot] | Same three |
| Listing | `url` and `github` entries in `hoaj/plugins`, plus its own Cursor marketplace | Same |
| Version bump | [By hand, not checked by CI][scc-bump] | Checked by CI |
| Version tags and releases | None | `vX.Y.Z`, immutable, with assets |
| `skills` key | Lists each skill | Can be left out if every folder under `skills/` is a skill, since all three agents scan that folder by default |

Do not add a root `plugin.json`. With an Agent Plugins `$schema` it [takes precedence in Copilot CLI][copilot-ref] and switches the plugin to a closed format.

## Not verified from a primary source

- **Cursor:** where installed plugins are cached, how individual installs update, whether `version` controls updates, and whether the client accepts a remote URL in `source`. The docs and the schema disagree on the last point.
- **Copilot CLI:** how `copilot plugin update` decides that a newer version exists. The docs do not say and the CLI's implementation was not read.
- **Codex:** update behaviour comes from reading the source at the pinned commit. The docs do not describe it, and no install was run.
- **`gh` without login:** whether the verify commands work unauthenticated was not tested or found in the docs.
- **The proposed pipeline** has not been run, as this repo has no release yet.

[cc-manifest]: https://code.claude.com/docs/en/plugins/manifest-reference
[cc-market]: https://code.claude.com/docs/en/plugins/marketplace-reference
[cc-loading]: https://code.claude.com/docs/en/plugins/loading
[cc-host]: https://code.claude.com/docs/en/plugins/host-marketplace
[cc-deps]: https://code.claude.com/docs/en/plugins/dependencies
[cursor-ref]: https://cursor.com/docs/reference/plugins
[cursor-docs]: https://cursor.com/docs/plugins
[cursor-schema]: https://github.com/cursor/plugins/blob/792440e8a560a4a3f63748cdee70491ecd412982/schemas/marketplace.schema.json#L68
[cursor-market]: https://github.com/cursor/plugins/blob/792440e8a560a4a3f63748cdee70491ecd412982/.cursor-plugin/marketplace.json
[cursor-validate]: https://github.com/cursor/plugins/blob/792440e8a560a4a3f63748cdee70491ecd412982/scripts/validate-plugins.mjs#L140
[copilot-ref]: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference
[codex-build]: https://developers.openai.com/plugins/build/plugins
[codex-manifest-paths]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/exec-server-protocol/src/protocol.rs#L55-L59
[codex-market-paths]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/marketplace.rs#L20-L23
[codex-raw-entry]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/marketplace.rs#L1051
[codex-source-enum]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/marketplace.rs#L1100
[codex-source-skip]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/marketplace.rs#L593
[codex-plugin-root]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/store.rs#L118
[codex-auto-upgrade]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/manager.rs#L3191
[codex-list-refresh]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/manager.rs#L2196
[codex-version-check]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/loader.rs#L667
[codex-force-reinstall]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugins/src/manager.rs#L3313
[codex-local-version]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugin-common/src/installed.rs#L10
[codex-active-version]: https://github.com/openai/codex/blob/140815f19c05a24a70ebc273016bd54ff71ced7c/codex-rs/core-plugin-common/src/installed.rs#L47
[gh-immutable]: https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases
[gh-immutable-enable]: https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/preventing-changes-to-your-releases
[gh-verify]: https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity
[gh-attest-concept]: https://docs.github.com/en/actions/concepts/security/artifact-attestations
[gh-attest-howto]: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
[gh-supply]: https://docs.github.com/en/code-security/concepts/supply-chain-security/supply-chain-security
[gh-archives]: https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives
[gh-notes]: https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
[gh-assets]: https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/
[gh-create]: https://cli.github.com/manual/gh_release_create
[gh-281]: https://github.com/cli/cli/releases/tag/v2.81.0
[plugins-cursor]: https://github.com/hoaj/plugins/blob/66959ea3e75f68b84c02e6cefd0d2a266e6d02d8/README.md#L27
[plugins-release-rule]: https://github.com/hoaj/plugins/blob/66959ea3e75f68b84c02e6cefd0d2a266e6d02d8/README.md#L61
[plugins-listing-rule]: https://github.com/hoaj/plugins/blob/66959ea3e75f68b84c02e6cefd0d2a266e6d02d8/README.md#L65
[scc-claude]: https://github.com/hoaj/site-cli-creator/blob/8661dc8ae9d4b45ffddd62a28754123125548964/.claude-plugin/plugin.json
[scc-cursor]: https://github.com/hoaj/site-cli-creator/blob/8661dc8ae9d4b45ffddd62a28754123125548964/.cursor-plugin/plugin.json
[scc-copilot]: https://github.com/hoaj/site-cli-creator/blob/8661dc8ae9d4b45ffddd62a28754123125548964/.github/plugin/plugin.json
[scc-cursor-market]: https://github.com/hoaj/site-cli-creator/blob/8661dc8ae9d4b45ffddd62a28754123125548964/.cursor-plugin/marketplace.json
[scc-bump]: https://github.com/hoaj/site-cli-creator/blob/8661dc8ae9d4b45ffddd62a28754123125548964/.claude/skills/improve-site-cli-creator/references/bump.md#L3
