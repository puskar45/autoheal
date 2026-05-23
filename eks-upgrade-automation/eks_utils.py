#!/usr/bin/env python3
from __future__ import annotations
"""
Shared utilities for EKS Non-Production Upgrade Automation.
AWS helpers, health checks, email, inventory loading.
"""

import argparse
import json
import logging
import subprocess
import os
import time
from datetime import datetime, timezone

import boto3
import yaml
from botocore.exceptions import ClientError

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
except ImportError:
    class _NoColor:
        def __getattr__(self, _):
            return ""
    Fore = Style = _NoColor()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("eks-upgrade")


# ─── Inventory ────────────────────────────────────────────────────────────────

def load_inventory(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_clusters(inv: dict, cluster_filter: str | None, env_filter: str | None = None) -> list[dict]:
    defaults = inv.get("defaults", {})
    clusters = []
    for c in inv["clusters"]:
        cluster = {**defaults, **c}
        if cluster_filter and cluster["name"] != cluster_filter:
            continue
        if env_filter and cluster.get("env", "").lower() != env_filter.lower():
            continue
        clusters.append(cluster)
    return clusters


# ─── AWS helpers ──────────────────────────────────────────────────────────────

def get_eks_client(cluster: dict):
    session_kwargs = {"region_name": cluster["region"]}
    profile = cluster.get("profile")
    if profile:
        session_kwargs["profile_name"] = profile
    session = boto3.Session(**session_kwargs)
    return session.client("eks")


def validate_profiles(clusters: list[dict]) -> bool:
    profiles_checked: set[str] = set()
    all_ok = True
    for cluster in clusters:
        profile = cluster.get("profile", "default")
        region = cluster["region"]
        key = f"{profile}:{region}"
        if key in profiles_checked:
            continue
        profiles_checked.add(key)
        try:
            session_kwargs = {"region_name": region}
            if profile and profile != "default":
                session_kwargs["profile_name"] = profile
            session = boto3.Session(**session_kwargs)
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            log.info(f"  ✓ Profile '{profile}' ({region}) → Account {identity['Account']}")
        except Exception as e:
            log.error(f"  ✗ Profile '{profile}' ({region}) → FAILED: {e}")
            all_ok = False
    return all_ok


def discover_nodegroups(client, cluster_name: str) -> list[str]:
    groups = []
    paginator = client.get_paginator("list_nodegroups")
    for page in paginator.paginate(clusterName=cluster_name):
        groups.extend(page["nodegroups"])
    return sorted(groups)


def discover_addons(client, cluster_name: str) -> list[str]:
    addons = []
    paginator = client.get_paginator("list_addons")
    for page in paginator.paginate(clusterName=cluster_name):
        addons.extend(page["addons"])
    return sorted(addons)


def get_cluster_version(client, cluster_name: str) -> str:
    return client.describe_cluster(name=cluster_name)["cluster"]["version"]


def get_nodegroup_info(client, cluster_name: str, ng_name: str) -> dict:
    return client.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng_name)["nodegroup"]


def get_addon_info(client, cluster_name: str, addon_name: str) -> dict:
    return client.describe_addon(clusterName=cluster_name, addonName=addon_name)["addon"]


def get_latest_addon_version(client, addon_name: str, cluster_version: str) -> str | None:
    """Find the most recent compatible version of an addon for the given k8s version."""
    try:
        resp = client.describe_addon_versions(
            addonName=addon_name, kubernetesVersion=cluster_version,
        )
        for addon_info in resp.get("addons", []):
            versions = addon_info.get("addonVersions", [])
            if not versions:
                continue
            compatible = []
            for v in versions:
                for compat in v.get("compatibilities", []):
                    if compat.get("clusterVersion") == cluster_version:
                        compatible.append(v["addonVersion"])
                        break
            if not compatible:
                compatible = [v["addonVersion"] for v in versions]
            import re
            def version_key(ver: str):
                nums = re.findall(r'\d+', ver)
                return [int(n) for n in nums]
            compatible.sort(key=version_key, reverse=True)
            return compatible[0]
    except ClientError as e:
        log.warning(f"  Could not look up versions for addon '{addon_name}': {e}")
    return None


# ─── Wait helpers ─────────────────────────────────────────────────────────────

def wait_for_nodegroup_active(client, cluster_name: str, ng_name: str,
                               timeout: int, poll_interval: int) -> bool:
    log.info(f"  Waiting for node group '{ng_name}' to become ACTIVE...")
    elapsed = 0
    while elapsed < timeout:
        try:
            status = get_nodegroup_info(client, cluster_name, ng_name)["status"]
            if status == "ACTIVE":
                log.info(f"  ✓ Node group '{ng_name}' is ACTIVE")
                return True
            if status in ("CREATE_FAILED", "DELETE_FAILED", "DEGRADED"):
                log.error(f"  ✗ Node group '{ng_name}' entered bad state: {status}")
                return False
            log.info(f"  Node group '{ng_name}' status: {status} ({elapsed}s elapsed)")
        except ClientError as e:
            log.warning(f"  Error checking node group: {e}")
        time.sleep(poll_interval)
        elapsed += poll_interval
    log.error(f"  ✗ Timed out waiting for node group '{ng_name}' after {timeout}s")
    return False


def wait_for_addon_active(client, cluster_name: str, addon_name: str,
                           timeout: int, poll_interval: int) -> bool:
    log.info(f"  Waiting for addon '{addon_name}' to become ACTIVE...")
    elapsed = 0
    while elapsed < timeout:
        try:
            status = get_addon_info(client, cluster_name, addon_name)["status"]
            if status == "ACTIVE":
                log.info(f"  ✓ Addon '{addon_name}' is ACTIVE")
                return True
            if status in ("CREATE_FAILED", "DELETE_FAILED", "DEGRADED"):
                log.error(f"  ✗ Addon '{addon_name}' entered bad state: {status}")
                return False
            log.info(f"  Addon '{addon_name}' status: {status} ({elapsed}s elapsed)")
        except ClientError as e:
            log.warning(f"  Error checking addon: {e}")
        time.sleep(poll_interval)
        elapsed += poll_interval
    log.error(f"  ✗ Timed out waiting for addon '{addon_name}' after {timeout}s")
    return False


def find_in_progress_update(client, cluster_name: str) -> str | None:
    """Find an existing in-progress version update for the cluster."""
    try:
        resp = client.list_updates(name=cluster_name)
        for update_id in resp.get("updateIds", []):
            update = client.describe_update(name=cluster_name, updateId=update_id)["update"]
            if update["type"] == "VersionUpdate" and update["status"] == "InProgress":
                log.info(f"  Found existing in-progress update: {update_id}")
                return update_id
    except ClientError as e:
        log.warning(f"  Could not list cluster updates: {e}")
    return None


def wait_for_cluster_update(client, cluster_name: str, update_id: str,
                             timeout: int, poll_interval: int) -> bool:
    """Poll the actual update object until it completes, not just cluster status."""
    log.info(f"  Waiting for cluster update '{update_id}' to complete...")
    elapsed = 0
    while elapsed < timeout:
        try:
            update = client.describe_update(
                name=cluster_name, updateId=update_id,
            )["update"]
            status = update["status"]
            if status == "Successful":
                log.info(f"  ✓ Cluster '{cluster_name}' update completed successfully")
                return True
            if status in ("Failed", "Cancelled"):
                errors = update.get("errors", [])
                error_msgs = "; ".join(e.get("errorMessage", "") for e in errors) if errors else "unknown"
                log.error(f"  ✗ Cluster update {status}: {error_msgs}")
                return False
            log.info(f"  Cluster update status: {status} ({elapsed}s elapsed)")
        except ClientError as e:
            log.warning(f"  Error checking cluster update: {e}")
        time.sleep(poll_interval)
        elapsed += poll_interval
    log.error(f"  ✗ Timed out waiting for cluster update after {timeout}s")
    return False


# ─── kubectl helper ───────────────────────────────────────────────────────────

def _run_kubectl(cluster_name: str, region: str, profile: str, kubectl_args: list[str],
                  timeout_sec: int = 30) -> tuple[bool, str]:
    """Run a kubectl command against a cluster. Returns (success, output)."""
    kubeconfig_path = f"/tmp/kubeconfig-{cluster_name}"
    cmd = [
        "aws", "eks", "update-kubeconfig",
        "--name", cluster_name,
        "--region", region,
        "--profile", profile,
        "--kubeconfig", kubeconfig_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"Failed to update kubeconfig: {e}"

    env = dict(**os.environ, KUBECONFIG=kubeconfig_path)
    full_cmd = ["kubectl"] + kubectl_args
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout_sec, env=env)
        return result.returncode == 0, result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)
    finally:
        try:
            os.remove(kubeconfig_path)
        except OSError:
            pass


# ─── Health checks ────────────────────────────────────────────────────────────

def validate_nodes(cluster_name: str, region: str, profile: str) -> tuple[bool, list[dict]]:
    """Check that all nodes are in Ready state."""
    ok, output = _run_kubectl(cluster_name, region, profile,
                               ["get", "nodes", "-o", "json"])
    if not ok:
        log.error(f"  ✗ Could not get nodes: {output}")
        return False, [{"check": "nodes", "status": "error", "detail": output}]

    try:
        nodes = json.loads(output)
    except json.JSONDecodeError:
        return False, [{"check": "nodes", "status": "error", "detail": "Invalid JSON from kubectl"}]

    results = []
    all_ready = True
    for node in nodes.get("items", []):
        name = node["metadata"]["name"]
        conditions = {c["type"]: c["status"] for c in node.get("status", {}).get("conditions", [])}
        ready = conditions.get("Ready") == "True"
        if not ready:
            all_ready = False
        results.append({
            "check": "node",
            "name": name,
            "status": "ready" if ready else "not_ready",
        })

    log.info(f"  Nodes: {len(results)} total, "
             f"{sum(1 for r in results if r['status'] == 'ready')} ready, "
             f"{sum(1 for r in results if r['status'] == 'not_ready')} not ready")
    return all_ready, results


def validate_pods(cluster_name: str, region: str, profile: str) -> tuple[bool, list[dict]]:
    """Check that all pods across all namespaces are Running/Succeeded."""
    all_ok = True
    results = []

    ok, output = _run_kubectl(cluster_name, region, profile,
                               ["get", "pods", "--all-namespaces", "-o", "json"])
    if not ok:
        log.error(f"  ✗ Could not get pods: {output}")
        return False, [{"check": "pods", "namespace": "all", "status": "error", "detail": output}]

    try:
        pods = json.loads(output)
    except json.JSONDecodeError:
        return False, [{"check": "pods", "namespace": "all", "status": "error", "detail": "Invalid JSON"}]

    ns_stats = {}
    for pod in pods.get("items", []):
        ns = pod["metadata"]["namespace"]
        pod_name = pod["metadata"]["name"]
        phase = pod.get("status", {}).get("phase", "Unknown")
        reason = pod.get("status", {}).get("reason", "")

        # Use reason if available (e.g. Evicted, OOMKilled) for more accurate display
        display_status = reason if reason else phase

        if ns not in ns_stats:
            ns_stats[ns] = {"healthy": 0, "unhealthy": 0, "unhealthy_pods": []}

        if phase in ("Running", "Succeeded"):
            ns_stats[ns]["healthy"] += 1
        else:
            ns_stats[ns]["unhealthy"] += 1
            ns_stats[ns]["unhealthy_pods"].append(f"{pod_name} ({display_status})")

    for ns in sorted(ns_stats):
        stats = ns_stats[ns]
        if stats["unhealthy"] > 0:
            all_ok = False

        results.append({
            "check": "pods",
            "namespace": ns,
            "status": "healthy" if stats["unhealthy"] == 0 else "unhealthy",
            "healthy": stats["healthy"],
            "unhealthy": stats["unhealthy"],
            "unhealthy_pods": stats["unhealthy_pods"],
        })
        log.info(f"  Pods in {ns}: {stats['healthy']} healthy, {stats['unhealthy']} unhealthy")
        if stats["unhealthy_pods"]:
            for p in stats["unhealthy_pods"][:5]:
                log.warning(f"    ⚠ {p}")
            if len(stats["unhealthy_pods"]) > 5:
                log.warning(f"    ... and {len(stats['unhealthy_pods']) - 5} more")

    return all_ok, results


def validate_addons_health(client, cluster_name: str) -> tuple[bool, list[dict]]:
    """Check that all EKS addons report ACTIVE status."""
    addons = discover_addons(client, cluster_name)
    all_ok = True
    results = []
    for addon in addons:
        info = get_addon_info(client, cluster_name, addon)
        status = info["status"]
        healthy = status == "ACTIVE"
        if not healthy:
            all_ok = False
        results.append({"check": "addon", "name": addon, "status": status})
        icon = "✓" if healthy else "✗"
        log.info(f"  {icon} Addon '{addon}': {status}")
    return all_ok, results


def get_eks_insights(client, cluster_name: str) -> list[dict]:
    """Fetch EKS upgrade insights for the cluster."""
    insights = []
    try:
        paginator = client.get_paginator("list_insights")
        for page in paginator.paginate(clusterName=cluster_name):
            for item in page.get("insights", []):
                insight_id = item.get("id", "")
                try:
                    detail = client.describe_insight(
                        clusterName=cluster_name, id=insight_id,
                    ).get("insight", {})
                    insights.append({
                        "id": insight_id,
                        "name": detail.get("name", ""),
                        "category": detail.get("category", ""),
                        "status": detail.get("insightStatus", {}).get("status", "UNKNOWN"),
                        "description": detail.get("description", ""),
                        "recommendation": detail.get("recommendation", ""),
                    })
                except ClientError:
                    insights.append({
                        "id": insight_id,
                        "name": item.get("name", ""),
                        "category": item.get("category", ""),
                        "status": item.get("insightStatus", {}).get("status", "UNKNOWN"),
                        "description": "",
                        "recommendation": "",
                    })
    except ClientError as e:
        log.warning(f"  Could not fetch EKS insights: {e}")
    except Exception as e:
        log.warning(f"  Could not fetch EKS insights: {e}")
    return insights


# ─── Email helper ─────────────────────────────────────────────────────────────

def _send_ses_email(subject: str, html_body: str, recipients: list[str],
                     sender: str, ses_region: str, ses_profile: str | None):
    """Send an HTML email via AWS SES."""
    try:
        session_kwargs = {"region_name": ses_region}
        if ses_profile:
            session_kwargs["profile_name"] = ses_profile
        session = boto3.Session(**session_kwargs)
        ses = session.client("ses")
        ses.send_email(
            Source=sender,
            Destination={"ToAddresses": recipients},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
            },
        )
        log.info(f"📧 Email report sent to: {', '.join(recipients)}")
    except ClientError as e:
        log.error(f"Failed to send email report: {e}")
        log.error("Make sure the sender address is verified in SES and you have ses:SendEmail permission")


# ─── Common argparse arguments ────────────────────────────────────────────────

def add_common_args(parser: argparse.ArgumentParser):
    """Add CLI arguments shared across all scripts."""
    parser.add_argument("--cluster", default=None,
                        help="Target a single cluster by name")
    parser.add_argument("--env", default="NonProd", choices=["NonProd", "Prod"],
                        help="Environment label for email subjects (default: NonProd)")
    parser.add_argument("--inventory", default="inventory.yaml",
                        help="Path to inventory file (default: inventory.yaml)")
    parser.add_argument("--email-to", nargs="+", default=None,
                        help="Email recipients for the report")
    parser.add_argument("--email-from", default="eks-upgrades@cedargate.com",
                        help="Sender email address (must be verified in SES)")
    parser.add_argument("--ses-region", default="us-east-1",
                        help="AWS region for SES (default: us-east-1)")
    parser.add_argument("--ses-profile", default=None,
                        help="AWS profile for SES (if different from cluster profiles)")
