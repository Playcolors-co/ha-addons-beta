# Publishing — beta channel ↔ stable repositories

Maintainer notes. This repo is the **single beta channel** for every Playcolors.co Home Assistant
project; each project is promoted to its **own public stable repository** when it's proven.

## Component map

| Component | Kind | Path in this repo | Identity | Stable repository |
|---|---|---|---|---|
| EBO for Home Assistant | Add-on | `ebo/` | slug `ebo` | [`Playcolors-co/ha-enabot`](https://github.com/Playcolors-co/ha-enabot) |
| EBO Local | Integration (HACS) | `custom_components/ebo_local/` | domain `ebo_local` | [`Playcolors-co/ha-ebo-local`](https://github.com/Playcolors-co/ha-ebo-local) |

Projects that are **not** hosted here, for reference — their beta lives in their own repository:

| Component | Kind | Beta channel | Repository |
|---|---|---|---|
| BinHass — Waltham Forest bin collections | Integration (HACS) | GitHub **pre-releases** in the same repo (HACS → repository → *Show beta versions*) | [`Playcolors-co/ha-binhass`](https://github.com/Playcolors-co/ha-binhass) |

The `ebo` add-on **bundles** its own native integration at `ebo/ha_integration/custom_components/ebo`
and installs it into the Home Assistant config dir at start-up. That is *not* a HACS integration —
it is nested inside the add-on folder, where HACS never looks. It needs no entry of its own here.

## Layout rules

- **Add-on** = one top-level folder containing `config.yaml`. Supervisor scans top-level folders only
  and silently skips anything without a `config.yaml` — so `custom_components/`, `.github/` and the
  docs are invisible to it. Adding an add-on is free: new folder, and add its name to the `addon`
  matrix in `.github/workflows/build.yml`.
- **HACS integration** = `custom_components/<domain>/` at the repo root, described by the root
  `hacs.json`. HACS downloads *only* that subtree, so the add-on folders never reach the user's
  config dir.
- **Exactly one HACS integration per repository, per category.** HACS resolves the integration by
  taking the **first directory** under `custom_components/`. A second one is not merely unreachable:
  whichever sorts first *takes the slot*, so an already-downloaded integration would be swapped out
  from under its users on the next refresh. Never add a second folder here.
  A component that must be staged in this repo anyway goes somewhere HACS does not look — e.g.
  `integrations/<name>/custom_components/<domain>/` — and is tested by copying it into
  `/config/custom_components`.
  For a standalone integration, the lighter option is **no second repo at all**: keep one public repo
  and ship betas as GitHub **pre-releases**, which testers opt into with *Show beta versions* on that
  repository in HACS. That is how BinHass works (table above).
  Other HACS *categories* (a Lovelace plugin, a theme) can share this repo: they are added in HACS
  as the same URL under a different category.
- **No releases/tags in this repo.** With no GitHub release present, HACS tracks the default branch
  and reads the version from `manifest.json`; Supervisor reads `version:` from each `config.yaml`.
  Creating a release here would make HACS treat that tag as the integration version — avoid it.

## Promote a beta to stable

The beta and the stable copy differ **only** in the identity fields below. Everything else is a
straight copy of the same source tree.

### Add-on `ebo` → `ha-enabot`

`rsync -a --delete` the add-on folder, then restore in `ebo/config.yaml`:

| Field | This repo (beta) | `ha-enabot` (stable) |
|---|---|---|
| `name` | `EBO for Home Assistant (unofficial, beta)` | `EBO for Home Assistant (unofficial)` |
| `url` | `https://github.com/Playcolors-co/ha-addons-beta` | `https://github.com/Playcolors-co/ha-enabot` |

Verify before committing: the repo root must contain exactly one add-on folder named `ebo`
(a stray folder does **not** raise an error — it silently creates a duplicate add-on and Home
Assistant keeps showing the old version), and
`grep -E '^(name|version|slug|url):' ebo/config.yaml` must match the table.

### Integration `ebo_local` → `ha-ebo-local`

`rsync -a --delete --exclude=__pycache__` the `custom_components/ebo_local/` tree, then restore in
the root `hacs.json`:

| Field | This repo (beta) | `ha-ebo-local` (stable) |
|---|---|---|
| `name` | `EBO Local (unofficial, beta)` | `EBO Local (unofficial)` |

`manifest.json` is **identical** in both channels (same domain, same version) — the domain is the
install identity, so it must not be renamed for beta.

## Branch protection

`main` is protected on this repo and on the stable ones: no force-push, no deletion, PR required
with three green checks (`Build add-on image (ebo)`, `Unit / security / technical / E2E (mocked)`,
`Lint + SAST + dependency audit`), 0 approvals.

```
git checkout -b <branch> && git commit … && git push -u origin <branch>
gh pr create … && gh pr merge --squash --delete-branch
```

The workflows have **no `paths:` filters on purpose**: all three checks must run on every PR,
including PRs that only touch `custom_components/`. Adding a path filter would make a required check
*skip* instead of pass, and GitHub would block the merge permanently. CI currently covers the
add-ons only — the integration is validated in its own stable repo.

## Secrets

Both channels are **public**. Vendor SDK licences, device tokens, Kalay/Agora credentials and
account passwords never enter this repo: they are supplied by the user through the config flow or
the add-on options, and the vendor binaries stay outside of git.
