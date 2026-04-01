# EKS Upgrade Automation

Automates monthly node group/addon upgrades and quarterly control plane upgrades for EKS clusters across multiple AWS accounts. Supports both NonProd and Prod environments.

## Files

| File | Purpose |
|------|---------|
| `eks_utils.py` | Shared: AWS helpers, health checks, email, inventory |
| `discover.py` | Pre-update discovery and reporting |
| `upgrade.py` | EKS version, addon, and nodegroup upgrades (no email, no validation) |
| `validate.py` | Post-update validation (versions, health, insights) with email report |
| `inventory.yaml` | Cluster inventory (names, regions, profiles, env) |
| `Jenkinsfile` | Jenkins pipeline with parameterized build (mode, cluster, env, dry-run) |
| `requirements.txt` | Python dependencies (boto3, pyyaml, colorama) |

## Setup

```bash
pip install -r requirements.txt
```

1. Edit `inventory.yaml` with your cluster names, regions, AWS CLI profiles, and `env` (NonProd/Prod)
2. Make sure `~/.aws/config` has named profiles for each account
3. Log in before running: `aws sso login --profile dev-account`

## Inventory

Each cluster in `inventory.yaml` has an `env` field (`NonProd` or `Prod`) used for filtering and email subjects:

```yaml
clusters:
  - name: eks-cap-dev-datawing
    region: us-east-1
    profile: CGTCitraHealth
    env: NonProd

  - name: eks-prod-datawing
    region: us-east-1
    profile: CGTCitraHealthProd
    env: Prod
```

## Usage

### Discovery (pre-update)
```bash
python discover.py                                          # All NonProd clusters (default)
python discover.py --env Prod                               # All Prod clusters
python discover.py --cluster eks-cap-dev-datawing            # Single cluster
python discover.py --email-to team@example.com               # Discover + email report
```

### Upgrades

`--cluster` is required for all upgrade modes.

```bash
# Monthly: addons + node groups (addons first, then node groups)
python upgrade.py --mode nodegroup_addon --cluster eks-non-prod-analytics

# Node groups only
python upgrade.py --mode nodegroup --cluster eks-cap-dev-datawing
python upgrade.py --mode nodegroup --cluster eks-cap-dev-datawing --dry-run

# Addons only
python upgrade.py --mode addon --cluster eks-cap-dev-datawing

# Control plane only (quarterly)
python upgrade.py --mode cluster --target-version 1.34 --cluster eks-cap-dev-datawing

# Full upgrade: control plane → addons → node groups (quarterly)
python upgrade.py --mode all --target-version 1.34 --cluster eks-cap-dev-datawing

# Prod cluster upgrade
python upgrade.py --mode nodegroup_addon --cluster eks-prod-datawing --env Prod
```

### Validation (post-update)
```bash
python validate.py                                          # All NonProd clusters
python validate.py --env Prod                               # All Prod clusters
python validate.py --cluster eks-cap-dev-datawing            # Single cluster
python validate.py --email-to team@example.com               # Validate + email report
python validate.py --env Prod --email-to team@example.com    # Prod validation + email
```

## Common Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--cluster` | Target a single cluster by name | All clusters |
| `--env` | Filter by environment (`NonProd` / `Prod`), also used in email subjects | `NonProd` |
| `--inventory` | Path to inventory file | `inventory.yaml` |
| `--dry-run` | Show what would happen without making changes (upgrade.py only) | Off |
| `--email-to` | Email recipients for the report | None |
| `--email-from` | Sender email (must be SES-verified) | `eks-upgrades@cedargate.com` |
| `--ses-region` | AWS region for SES | `us-east-1` |
| `--ses-profile` | AWS profile for SES (if different from cluster profiles) | None |

## How It Works

- Reads cluster list from `inventory.yaml` (each cluster has its own AWS profile and env label)
- Filters clusters by `--env` and/or `--cluster` flags
- Validates all AWS profiles can authenticate before starting
- Auto-discovers node groups and addons from AWS (no hardcoding)
- Node group update detection uses SSM parameters (supports AL2, AL2023, Bottlerocket x86/ARM, GPU)
- Node groups are upgraded in parallel (all kicked off at once, polled together)
- Addons upgrade to the latest compatible version with `resolveConflicts=NONE`
- If a resource already has an update in progress, the script waits for it to finish instead of skipping
- Cluster version upgrade tracks the actual update object (not just cluster status) to avoid moving on prematurely
- Temporary kubeconfig files (`/tmp/kubeconfig-{cluster}`) are cleaned up after each kubectl command
- Validation checks: cluster version, addon versions (latest check), node group AMI (latest check), node kubelet versions, pod health, EKS insights
- Designed for Jenkins: one job per cluster via `--cluster`, run `validate.py` after all jobs complete for a consolidated report

## Email Reports

- `discover.py --email-to` — pre-update discovery report (not sent if any cluster fails)
- `validate.py --email-to` — post-update validation report with tables for addons, node groups, and nodes
- `upgrade.py` does not send emails — run `validate.py` separately after upgrades complete
- Email subjects use the `--env` value: `EKS {env} Post-Update Validation - YYYY/MM/DD`

The sender address must be verified in SES. If SES is in a different account, use `--ses-profile`.

## Jenkins Pipeline

The included `Jenkinsfile` provides a parameterized pipeline with three modes:

- `discover` — runs `discover.py` for all clusters in the selected env
- `upgrade` — runs `upgrade.py` for a single cluster (one job per cluster)
- `validate` — runs `validate.py` for all or a single cluster

Parameters are dynamic: `UPGRADE_TARGET`, `CLUSTER`, `TARGET_VERSION`, and `DRY_RUN` only appear when relevant to the selected mode. Requires the Jenkins Active Choices plugin.
