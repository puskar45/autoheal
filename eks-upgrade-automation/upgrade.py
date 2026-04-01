#!/usr/bin/env python3
from __future__ import annotations
"""
EKS Upgrade Automation — Upgrades only (no validation, no email).

Usage:
  python upgrade.py --mode nodegroup_addon --cluster CLUSTER   # Monthly: addons then node groups
  python upgrade.py --mode nodegroup --cluster CLUSTER         # Node groups only
  python upgrade.py --mode addon --cluster CLUSTER             # Addons only
  python upgrade.py --mode cluster --target-version 1.34 --cluster CLUSTER   # Quarterly: control plane
  python upgrade.py --mode all --target-version 1.34 --cluster CLUSTER       # Full upgrade

Options:
  --cluster CLUSTER_NAME (required)       # Target cluster
  --env NonProd|Prod                      # Environment filter (optional)
  --dry-run                               # Show what would happen without making changes
"""

import argparse
import sys

from botocore.exceptions import ClientError

from eks_utils import (
    Fore, Style, log,
    load_inventory, get_clusters, get_eks_client, validate_profiles,
    discover_nodegroups, discover_addons, get_cluster_version,
    get_nodegroup_info, get_addon_info, get_latest_addon_version,
    wait_for_nodegroup_active, wait_for_addon_active, wait_for_cluster_update,
    find_in_progress_update,
)


# ─── Upgrade operations ──────────────────────────────────────────────────────

def upgrade_nodegroups(client, cluster: dict, dry_run: bool) -> tuple[bool, list[dict]]:
    cluster_name = cluster["name"]
    timeout = cluster.get("timeout", 3600)
    poll_interval = cluster.get("poll_interval", 30)
    details = []

    nodegroups = discover_nodegroups(client, cluster_name)
    if not nodegroups:
        log.warning(f"  No managed node groups found for '{cluster_name}'")
        return True, details

    log.info(f"  Found {len(nodegroups)} node group(s): {', '.join(nodegroups)}")

    if dry_run:
        for ng in nodegroups:
            info = get_nodegroup_info(client, cluster_name, ng)
            current_version = info.get("releaseVersion", "unknown")
            log.info(f"  [DRY RUN] Would upgrade node group '{ng}' (current: {current_version})")
            details.append({"name": ng, "before": current_version, "after": None, "status": "dry_run"})
        return True, details

    # Step 1: Kick off all node group updates
    pending = []  # node groups we need to wait on
    for ng in nodegroups:
        info = get_nodegroup_info(client, cluster_name, ng)
        current_version = info.get("releaseVersion", "unknown")
        log.info(f"  Node group '{ng}' current release: {current_version}")
        entry = {"name": ng, "before": current_version, "after": None, "status": "unknown"}

        try:
            log.info(f"  Initiating upgrade for node group '{ng}'...")
            client.update_nodegroup_version(clusterName=cluster_name, nodegroupName=ng)
            pending.append(entry)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "ResourceInUseException":
                log.warning(f"  Node group '{ng}' already has an update in progress")
                pending.append(entry)
            elif "No updates are needed" in str(e):
                log.info(f"  ✓ Node group '{ng}' is already on the latest version")
                entry["status"] = "up_to_date"
                entry["after"] = current_version
                details.append(entry)
            else:
                log.error(f"  ✗ Failed to initiate upgrade for node group '{ng}': {e}")
                entry["status"] = "failed"
                entry["error"] = str(e)
                details.append(entry)

    if not pending:
        all_ok = all(e["status"] != "failed" for e in details)
        return all_ok, details

    # Step 2: Wait for all pending node groups to finish
    log.info(f"  Waiting for {len(pending)} node group(s) to finish updating...")
    all_ok = all(e["status"] != "failed" for e in details)

    import time
    elapsed = 0
    while pending and elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval
        still_pending = []
        for entry in pending:
            ng = entry["name"]
            try:
                info = get_nodegroup_info(client, cluster_name, ng)
                status = info["status"]
                if status == "ACTIVE":
                    entry["after"] = info.get("releaseVersion", "unknown")
                    entry["status"] = "upgraded"
                    log.info(f"  ✓ Node group '{ng}' is ACTIVE (release: {entry['after']})")
                    details.append(entry)
                elif status in ("CREATE_FAILED", "DELETE_FAILED", "DEGRADED"):
                    entry["status"] = "failed"
                    log.error(f"  ✗ Node group '{ng}' entered bad state: {status}")
                    details.append(entry)
                    all_ok = False
                else:
                    still_pending.append(entry)
            except ClientError as e:
                log.warning(f"  Error checking node group '{ng}': {e}")
                still_pending.append(entry)
        pending = still_pending
        if pending:
            names = ", ".join(e["name"] for e in pending)
            log.info(f"  Still updating ({elapsed}s elapsed): {names}")

    # Timed out entries
    for entry in pending:
        log.error(f"  ✗ Timed out waiting for node group '{entry['name']}' after {timeout}s")
        entry["status"] = "failed"
        details.append(entry)
        all_ok = False

    return all_ok, details


def upgrade_addons(client, cluster: dict, dry_run: bool) -> tuple[bool, list[dict]]:
    cluster_name = cluster["name"]
    addon_timeout = 300       # 5 minutes
    addon_poll = 10           # poll every 10 seconds
    details = []

    cluster_version = get_cluster_version(client, cluster_name)
    addons = discover_addons(client, cluster_name)
    if not addons:
        log.warning(f"  No addons found for '{cluster_name}'")
        return True, details

    log.info(f"  Found {len(addons)} addon(s): {', '.join(addons)}")
    all_ok = True

    for addon in addons:
        info = get_addon_info(client, cluster_name, addon)
        current_version = info.get("addonVersion", "unknown")
        current_status = info["status"]
        entry = {"name": addon, "before": current_version, "after": None, "status": "unknown"}

        # Skip addons already in a bad state
        if current_status in ("CREATE_FAILED", "DELETE_FAILED", "DEGRADED"):
            log.error(f"  ✗ Addon '{addon}' is in {current_status} state — skipping upgrade")
            entry["status"] = "failed"
            entry["error"] = f"Addon already in {current_status} state"
            details.append(entry)
            all_ok = False
            continue

        latest_version = get_latest_addon_version(client, addon, cluster_version)

        if not latest_version:
            log.warning(f"  Could not determine latest version for addon '{addon}', skipping")
            entry["status"] = "skipped"
            details.append(entry)
            continue

        if current_version == latest_version:
            log.info(f"  ✓ Addon '{addon}' already at latest version ({current_version})")
            entry["status"] = "up_to_date"
            entry["after"] = current_version
            details.append(entry)
            continue

        log.info(f"  Addon '{addon}': {current_version} → {latest_version}")

        if dry_run:
            log.info(f"  [DRY RUN] Would upgrade addon '{addon}' to {latest_version}")
            entry["status"] = "dry_run"
            entry["after"] = latest_version
            details.append(entry)
            continue

        try:
            client.update_addon(
                clusterName=cluster_name, addonName=addon,
                addonVersion=latest_version, resolveConflicts="NONE",
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "ResourceInUseException":
                log.warning(f"  Addon '{addon}' already has an update in progress — waiting for it to finish...")
                if wait_for_addon_active(client, cluster_name, addon, addon_timeout, addon_poll):
                    new_info = get_addon_info(client, cluster_name, addon)
                    entry["after"] = new_info.get("addonVersion", "unknown")
                    entry["status"] = "upgraded"
                else:
                    entry["status"] = "failed"
                    all_ok = False
                details.append(entry)
                continue
            else:
                log.error(f"  ✗ Failed to upgrade addon '{addon}': {e}")
                entry["status"] = "failed"
                entry["error"] = str(e)
                details.append(entry)
                all_ok = False
                continue

        if wait_for_addon_active(client, cluster_name, addon, addon_timeout, addon_poll):
            entry["after"] = latest_version
            entry["status"] = "upgraded"
        else:
            entry["status"] = "failed"
            all_ok = False
        details.append(entry)

    return all_ok, details


def upgrade_cluster_version(client, cluster: dict, target_version: str,
                             dry_run: bool) -> tuple[bool, dict]:
    cluster_name = cluster["name"]
    timeout = cluster.get("timeout", 5400)
    poll_interval = cluster.get("poll_interval", 30)

    current_version = get_cluster_version(client, cluster_name)
    log.info(f"  Current control plane version: {current_version}")

    desired = target_version
    detail = {"before": current_version, "after": None, "status": "unknown"}

    if current_version == desired:
        log.info(f"  ✓ Cluster already at version {desired}")
        detail["status"] = "up_to_date"
        detail["after"] = current_version
        return True, detail

    log.info(f"  Control plane: {current_version} → {desired}")

    if dry_run:
        log.info(f"  [DRY RUN] Would upgrade control plane to {desired}")
        detail["status"] = "dry_run"
        detail["after"] = desired
        return True, detail

    try:
        resp = client.update_cluster_version(name=cluster_name, version=desired)
        log.info(f"  API response: {resp}")
        update_id = resp.get("update", {}).get("updateId") or resp.get("update", {}).get("id")
        if not update_id:
            log.warning(f"  Could not extract update ID from response — falling back to list_updates")
            update_id = find_in_progress_update(client, cluster_name)
        if update_id:
            log.info(f"  Update initiated — update ID: {update_id}")
        else:
            log.warning(f"  No update ID found — will poll cluster version directly")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ResourceInUseException":
            log.warning(f"  Cluster already has an update in progress — waiting for it to finish...")
            existing_update_id = find_in_progress_update(client, cluster_name)
            if existing_update_id:
                if wait_for_cluster_update(client, cluster_name, existing_update_id, timeout, poll_interval):
                    new_version = get_cluster_version(client, cluster_name)
                    detail["after"] = new_version
                    detail["status"] = "upgraded"
                    return True, detail
                else:
                    detail["status"] = "failed"
                    return False, detail
            else:
                log.warning(f"  Could not find the in-progress update — waiting 5 minutes and rechecking...")
                import time
                time.sleep(300)
                new_version = get_cluster_version(client, cluster_name)
                if new_version == desired:
                    detail["after"] = new_version
                    detail["status"] = "upgraded"
                    return True, detail
                detail["status"] = "failed"
                detail["error"] = "Update in progress but could not track it"
                return False, detail
        else:
            log.error(f"  ✗ Failed to upgrade cluster: {e}")
            detail["status"] = "failed"
            detail["error"] = str(e)
            return False, detail

    if update_id:
        if wait_for_cluster_update(client, cluster_name, update_id, timeout, poll_interval):
            detail["after"] = desired
            detail["status"] = "upgraded"
            return True, detail
        else:
            detail["status"] = "failed"
            return False, detail
    else:
        # No update ID — poll cluster version until it matches desired
        import time
        log.info(f"  Polling cluster version until it reaches {desired}...")
        elapsed = 0
        while elapsed < timeout:
            current = get_cluster_version(client, cluster_name)
            if current == desired:
                log.info(f"  ✓ Cluster version is now {desired}")
                detail["after"] = desired
                detail["status"] = "upgraded"
                return True, detail
            log.info(f"  Cluster version: {current} ({elapsed}s elapsed)")
            time.sleep(poll_interval)
            elapsed += poll_interval
        detail["status"] = "failed"
        detail["error"] = f"Timed out waiting for cluster to reach version {desired}"
        return False, detail


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def run_for_cluster(cluster: dict, mode: str, dry_run: bool,
                     target_version: str | None) -> dict:
    cluster_name = cluster["name"]
    region = cluster["region"]
    profile = cluster.get("profile", "default")

    header = f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}"
    print(header)
    log.info(f"{Fore.GREEN}Cluster: {cluster_name}  |  region: {region}  |  profile: {profile}{Style.RESET_ALL}")
    print(header)

    result = {
        "cluster": cluster_name,
        "region": region,
        "profile": profile,
        "success": True,
        "control_plane": None,
        "addons": [],
        "nodegroups": [],
    }

    client = get_eks_client(cluster)

    if mode in ("cluster", "all"):
        log.info(f"{Fore.YELLOW}── Control Plane Upgrade ──{Style.RESET_ALL}")
        ok, detail = upgrade_cluster_version(client, cluster, target_version, dry_run)
        result["control_plane"] = detail
        if not ok:
            result["success"] = False
            if mode == "all":
                log.error("  Control plane upgrade failed — skipping remaining steps")
                return result

    if mode in ("addon", "all", "nodegroup_addon"):
        log.info(f"{Fore.YELLOW}── Addon Upgrades ──{Style.RESET_ALL}")
        ok, details = upgrade_addons(client, cluster, dry_run)
        result["addons"] = details
        if not ok:
            result["success"] = False

    if mode in ("nodegroup", "all", "nodegroup_addon"):
        log.info(f"{Fore.YELLOW}── Node Group Upgrades ──{Style.RESET_ALL}")
        ok, details = upgrade_nodegroups(client, cluster, dry_run)
        result["nodegroups"] = details
        if not ok:
            result["success"] = False

    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="EKS Upgrade Automation",
        epilog="""
Examples:
  python upgrade.py --mode nodegroup_addon --cluster eks-cap-dev-datawing          # Monthly: addons + node groups
  python upgrade.py --mode nodegroup --cluster eks-cap-dev-datawing --dry-run      # Preview node group upgrades
  python upgrade.py --mode nodegroup --cluster eks-cap-dev-datawing                # Node groups only
  python upgrade.py --mode addon --cluster eks-cap-dev-datawing                    # Addons only
  python upgrade.py --mode cluster --target-version 1.34 --cluster eks-cap-dev-datawing   # Control plane
  python upgrade.py --mode all --target-version 1.34 --cluster eks-cap-dev-datawing       # Full upgrade
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--mode", required=True,
                        choices=["nodegroup", "addon", "cluster", "all", "nodegroup_addon"],
                        help="What to upgrade")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    parser.add_argument("--target-version", default=None,
                        help="Target k8s version for control plane upgrade (e.g. 1.31)")
    parser.add_argument("--cluster", required=True,
                        help="Target cluster name (required)")
    parser.add_argument("--inventory", default="inventory.yaml",
                        help="Path to inventory file (default: inventory.yaml)")
    parser.add_argument("--env", default=None, choices=["NonProd", "Prod"],
                        help="Filter clusters by environment")
    args = parser.parse_args()

    if args.mode in ("cluster", "all") and not args.target_version:
        parser.error("--target-version is required for --mode cluster and --mode all")

    inv = load_inventory(args.inventory)
    clusters = get_clusters(inv, args.cluster, args.env)

    if not clusters:
        log.error("No clusters matched the given filters")
        sys.exit(1)

    print(f"\n{Fore.CYAN}EKS Upgrade Automation{Style.RESET_ALL}")
    print(f"  Mode      : {args.mode}")
    print(f"  Dry run   : {args.dry_run}")
    print(f"  Clusters  : {len(clusters)}")
    for c in clusters:
        print(f"    - {c['name']} ({c['region']}, profile: {c.get('profile', 'default')})")
    print()

    log.info("Validating AWS profiles...")
    if not validate_profiles(clusters):
        log.error("Some AWS profiles failed authentication — fix credentials before proceeding")
        sys.exit(1)
    print()

    results = []
    for cluster in clusters:
        result = run_for_cluster(cluster, args.mode, args.dry_run, args.target_version)
        results.append(result)

    # Final summary
    print(f"\n{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  UPGRADE SUMMARY{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
    for r in results:
        status = f"{Fore.GREEN}✓ SUCCESS{Style.RESET_ALL}" if r["success"] else f"{Fore.RED}✗ FAILED{Style.RESET_ALL}"
        print(f"  {r['cluster']}: {status}")

    if all(r["success"] for r in results):
        log.info(f"{Fore.GREEN}All upgrades completed successfully{Style.RESET_ALL}")
    else:
        log.error(f"{Fore.RED}Some upgrades failed — review the output above{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    main()
