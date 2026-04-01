#!/usr/bin/env python3
from __future__ import annotations
"""
EKS Non-Production Discovery — Pre-update cluster state report.

Usage:
  python discover.py                                          # Discover all nonprod clusters
  python discover.py --cluster eks-cap-dev-datawing            # Single cluster
  python discover.py --email-to team@co.com                    # Discover + email report
"""

import argparse
import sys
from datetime import datetime, timezone

import boto3

from eks_utils import (
    Fore, Style, log,
    load_inventory, get_clusters, get_eks_client, validate_profiles,
    discover_nodegroups, discover_addons, get_cluster_version,
    get_nodegroup_info, get_addon_info, get_latest_addon_version,
    validate_addons_health, validate_nodes, validate_pods,
    get_eks_insights, _send_ses_email, add_common_args,
)


# ─── Discovery logic ─────────────────────────────────────────────────────────

def discover(client, cluster: dict) -> dict:
    """Discover cluster state: versions, update availability, health, insights."""
    cluster_name = cluster["name"]
    region = cluster["region"]
    profile = cluster.get("profile", "default")

    version = get_cluster_version(client, cluster_name)
    nodegroups = discover_nodegroups(client, cluster_name)
    addons_list = discover_addons(client, cluster_name)

    result = {
        "cluster": cluster_name,
        "region": region,
        "profile": profile,
        "k8s_version": version,
        "nodegroups": [],
        "addons": [],
        "health": [],
        "insights": [],
        "updates_available": False,
    }

    # Node groups with update check
    print(f"\n  Kubernetes version : {version}")
    print(f"  Node groups ({len(nodegroups)}):")
    for ng in nodegroups:
        info = get_nodegroup_info(client, cluster_name, ng)
        release = info.get("releaseVersion", "?")
        status = info["status"]
        desired = info["scalingConfig"]["desiredSize"]
        ami_type = info.get("amiType", "AL2_x86_64")

        ami_ssm_configs = {
            "AL2_x86_64":              {"path": f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2/recommended/release_version"},
            "AL2_x86_64_GPU":          {"path": f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2-gpu/recommended/release_version"},
            "AL2_ARM_64":              {"path": f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2-arm64/recommended/release_version"},
            "AL2023_x86_64_STANDARD":  {"path": f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2023/x86_64/standard/recommended/release_version"},
            "AL2023_ARM_64_STANDARD":  {"path": f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2023/arm64/standard/recommended/release_version"},
            "BOTTLEROCKET_x86_64":     {"path": f"/aws/service/bottlerocket/aws-k8s-{version}/x86_64/latest/image_version"},
            "BOTTLEROCKET_ARM_64":     {"path": f"/aws/service/bottlerocket/aws-k8s-{version}/arm64/latest/image_version"},
        }
        ssm_config = ami_ssm_configs.get(ami_type)

        ng_update_available = False
        latest_release = None
        if ssm_config:
            param_name = ssm_config["path"]
            try:
                session_kwargs = {"region_name": region}
                p = cluster.get("profile")
                if p:
                    session_kwargs["profile_name"] = p
                ssm = boto3.Session(**session_kwargs).client("ssm")
                param_resp = ssm.get_parameter(Name=param_name)
                latest_release = param_resp["Parameter"]["Value"]
                log.info(f"  Node group '{ng}': ami_type={ami_type}, current='{release}', latest='{latest_release}'")

                current_comparable = release.split("-")[0] if release else ""
                latest_comparable = latest_release.split("-")[0] if latest_release else ""

                if current_comparable and latest_comparable and current_comparable != latest_comparable:
                    ng_update_available = True
                    log.info(f"  → Update available for '{ng}' ({current_comparable} → {latest_comparable})")
                elif release and latest_release and release.strip() != latest_release.strip():
                    ng_update_available = True
                    log.info(f"  → Update available for '{ng}'")
                else:
                    log.info(f"  → '{ng}' is up to date")
            except Exception as e:
                log.warning(f"  SSM lookup failed for '{ng}' (ami_type={ami_type}, param={param_name}): {e}")
        else:
            log.warning(f"  Node group '{ng}' uses AMI type '{ami_type}' — not in SSM lookup map, skipping update check")

        if ng_update_available:
            result["updates_available"] = True
        tag = " ← UPDATE AVAILABLE" if ng_update_available else ""
        latest_str = f", latest: {latest_release}" if latest_release and ng_update_available else ""
        print(f"    - {ng}  (AMI type: {ami_type}, release: {release}{latest_str}, status: {status}, desired: {desired}){tag}")
        result["nodegroups"].append({
            "name": ng, "release": release, "latest_release": latest_release,
            "status": status, "desired": desired, "update_available": ng_update_available,
            "ami_type": ami_type,
        })

    # Addons with update check
    print(f"  Addons ({len(addons_list)}):")
    for addon in addons_list:
        info = get_addon_info(client, cluster_name, addon)
        current = info.get("addonVersion", "?")
        status = info["status"]
        latest = get_latest_addon_version(client, addon, version)
        update_available = bool(latest and latest != current)
        if update_available:
            result["updates_available"] = True
        tag = " ← UPDATE AVAILABLE" if update_available else ""
        print(f"    - {addon}  (current: {current}, latest: {latest or '?'}, status: {status}){tag}")
        result["addons"].append({
            "name": addon, "current": current, "latest": latest or "?",
            "status": status, "update_available": update_available,
        })

    # Health checks
    log.info("  Running health checks...")
    _, addon_checks = validate_addons_health(client, cluster_name)
    _, node_checks = validate_nodes(cluster_name, region, profile)
    _, pod_checks = validate_pods(cluster_name, region, profile)
    result["health"] = addon_checks + node_checks + pod_checks

    # EKS Insights
    log.info("  Fetching EKS insights...")
    insights = get_eks_insights(client, cluster_name)
    result["insights"] = insights
    if insights:
        print(f"  Insights ({len(insights)}):")
        for ins in insights:
            icon = "⚠" if ins["status"] != "PASSING" else "✓"
            print(f"    {icon} [{ins['category']}] {ins['name']} — {ins['status']}")
    else:
        print("  Insights: none")

    return result


# ─── Discovery report ─────────────────────────────────────────────────────────

def build_discovery_report(results: list[dict], env: str = "NonProd") -> tuple[str, str]:
    """Build an HTML discovery report with versions, updates, health, and insights."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total_updates = 0
    total_health_issues = 0
    total_insights_warning = 0

    for r in results:
        d = r.get("discovery", {})
        total_updates += sum(1 for a in d.get("addons", []) if a.get("update_available"))
        total_updates += sum(1 for ng in d.get("nodegroups", []) if ng.get("update_available"))
        total_health_issues += sum(1 for h in d.get("health", [])
                                    if h.get("status") not in ("ready", "healthy", "ACTIVE"))
        total_insights_warning += sum(1 for i in d.get("insights", [])
                                       if i.get("status") != "PASSING")

    date_str = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    subject = f"EKS {env} PreUpdate Summary - Discovery Mode - {date_str}"

    cluster_rows = []
    for r in results:
        d = r.get("discovery", {})
        cluster_name = d.get("cluster", r.get("cluster", "?"))
        region = d.get("region", r.get("region", "?"))
        profile = d.get("profile", r.get("profile", "?"))
        k8s_ver = d.get("k8s_version", "?")

        # Addons table
        addon_rows = []
        for a in d.get("addons", []):
            update_badge = '<span style="color:#dc3545;font-weight:bold;"> ⬆ UPDATE</span>' if a.get("update_available") else ""
            status_color = "#28a745" if a.get("status") == "ACTIVE" else "#dc3545"
            addon_rows.append(
                f'<tr><td style="padding:4px 8px;">{a["name"]}</td>'
                f'<td style="padding:4px 8px;">{a["current"]}</td>'
                f'<td style="padding:4px 8px;">{a["latest"]}{update_badge}</td>'
                f'<td style="padding:4px 8px;color:{status_color};">{a.get("status", "?")}</td></tr>'
            )

        # Node groups table
        ng_rows = []
        for ng in d.get("nodegroups", []):
            status_color = "#28a745" if ng.get("status") == "ACTIVE" else "#dc3545"
            release = ng.get("release", "?")
            if len(release) > 50:
                release = "..." + release[-40:]
            update_badge = '<span style="color:#dc3545;font-weight:bold;"> ⬆ UPDATE</span>' if ng.get("update_available") else ""
            ng_rows.append(
                f'<tr><td style="padding:4px 8px;">{ng["name"]}</td>'
                f'<td style="padding:4px 8px;">{release}{update_badge}</td>'
                f'<td style="padding:4px 8px;color:{status_color};">{ng.get("status", "?")}</td>'
                f'<td style="padding:4px 8px;">{ng.get("desired", "?")}</td></tr>'
            )

        # Health summary
        health_lines = []
        addon_checks = [h for h in d.get("health", []) if h.get("check") == "addon"]
        unhealthy_addons = [h for h in addon_checks if h["status"] != "ACTIVE"]
        if unhealthy_addons:
            for h in unhealthy_addons:
                health_lines.append(f'<span style="color:#dc3545;">⚠ Addon {h.get("name","")}: {h["status"]}</span>')
        else:
            health_lines.append('<span style="color:#28a745;">✓ All addons healthy</span>')

        node_checks = [h for h in d.get("health", []) if h.get("check") == "node"]
        unhealthy_nodes = [h for h in node_checks if h["status"] != "ready"]
        if unhealthy_nodes:
            for h in unhealthy_nodes:
                health_lines.append(f'<span style="color:#dc3545;">⚠ Node {h.get("name","")}: {h["status"]}</span>')
        else:
            health_lines.append(f'<span style="color:#28a745;">✓ All nodes ready ({len(node_checks)})</span>')

        pod_checks = [h for h in d.get("health", []) if h.get("check") == "pods"]
        total_healthy = sum(h.get("healthy", 0) for h in pod_checks)
        all_unhealthy_pods = []
        for h in pod_checks:
            ns = h.get("namespace", "")
            for p in h.get("unhealthy_pods", []):
                all_unhealthy_pods.append(f"{ns}/{p}")

        if all_unhealthy_pods:
            health_lines.append(f'<span style="color:#dc3545;">⚠ {len(all_unhealthy_pods)} unhealthy pod(s):</span>')
            for p in all_unhealthy_pods:
                health_lines.append(f'&nbsp;&nbsp;<span style="color:#dc3545;">⚠ {p}</span>')
        else:
            health_lines.append(f'<span style="color:#28a745;">✓ All pods healthy ({total_healthy})</span>')

        # Insights — only show failing ones
        insights = d.get("insights", [])
        failing_insights = [ins for ins in insights if ins.get("status") != "PASSING"]
        insight_lines = []
        if failing_insights:
            for ins in failing_insights:
                line = f'<span style="color:#dc3545;">⚠ [{ins.get("category","")}] {ins.get("name","")} — {ins["status"]}</span>'
                if ins.get("description"):
                    line += f'<br><small style="color:#666;">{ins["description"][:200]}</small>'
                if ins.get("recommendation"):
                    line += f'<br><small style="color:#0066cc;">Recommendation: {ins["recommendation"][:200]}</small>'
                insight_lines.append(line)
        else:
            insight_lines.append(f'<span style="color:#28a745;">✓ All insights passing ({len(insights)})</span>')

        has_issues = any(h.get("status") not in ("ready", "healthy", "ACTIVE")
                         for h in d.get("health", []))
        cluster_icon = "⚠" if has_issues else "✅"
        cluster_color = "#dc3545" if has_issues else "#28a745"

        cluster_rows.append(f"""
        <tr><td colspan="2" style="background:#232f3e;color:white;padding:10px;font-weight:bold;">
          <span style="color:{cluster_color};">{cluster_icon}</span> {cluster_name}
          &nbsp;<small style="color:#aaa;">{region} &middot; {profile} &middot; k8s {k8s_ver}</small>
        </td></tr>
        <tr><td colspan="2" style="padding:12px;">
          <b>Addons</b>
          <table style="width:100%;border-collapse:collapse;margin:8px 0;">
            <tr style="background:#f5f5f5;"><th style="padding:4px 8px;text-align:left;">Name</th>
            <th style="padding:4px 8px;text-align:left;">Current</th>
            <th style="padding:4px 8px;text-align:left;">Latest</th>
            <th style="padding:4px 8px;text-align:left;">Status</th></tr>
            {''.join(addon_rows) if addon_rows else '<tr><td colspan="4" style="padding:4px 8px;color:#888;">None</td></tr>'}
          </table>
          <b>Node Groups</b>
          <table style="width:100%;border-collapse:collapse;margin:8px 0;">
            <tr style="background:#f5f5f5;"><th style="padding:4px 8px;text-align:left;">Name</th>
            <th style="padding:4px 8px;text-align:left;">AMI Release</th>
            <th style="padding:4px 8px;text-align:left;">Status</th>
            <th style="padding:4px 8px;text-align:left;">Desired</th></tr>
            {''.join(ng_rows) if ng_rows else '<tr><td colspan="4" style="padding:4px 8px;color:#888;">None</td></tr>'}
          </table>
          <b>Health</b><br>
          {'<br>'.join(health_lines) if health_lines else '<span style="color:#888;">No health data</span>'}
          <br><br>
          <b>EKS Insights</b><br>
          {'<br>'.join(insight_lines) if insight_lines else '<span style="color:#888;">No insights</span>'}
        </td></tr>""")

    html = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#333;max-width:900px;margin:0 auto;padding:20px;">
      <h2 style="color:#232f3e;">EKS PreUpdate Summary - Discovery Mode</h2>
      <table style="margin-bottom:20px;">
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Timestamp:</td><td>{timestamp}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Clusters:</td><td>{len(results)}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Updates available:</td><td>{total_updates}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Health issues:</td><td style="color:{'#dc3545' if total_health_issues else '#28a745'};">{total_health_issues}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Insight warnings:</td><td style="color:{'#dc3545' if total_insights_warning else '#28a745'};">{total_insights_warning}</td></tr>
      </table>
      <table style="width:100%;border-collapse:collapse;border:1px solid #ddd;">
        {''.join(cluster_rows)}
      </table>
      <p style="color:#888;font-size:12px;margin-top:20px;">Generated by EKS Upgrade Automation — Discovery Mode</p>
    </body>
    </html>"""
    return subject, html


def send_discovery_report(results: list[dict], recipients: list[str], sender: str,
                           ses_region: str, ses_profile: str | None, env: str = "NonProd"):
    subject, html_body = build_discovery_report(results, env)
    _send_ses_email(subject, html_body, recipients, sender, ses_region, ses_profile)


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def run_discover_for_cluster(cluster: dict) -> dict:
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
    }

    try:
        client = get_eks_client(cluster)
        discovery = discover(client, cluster)
        result["discovery"] = discovery
    except Exception as e:
        log.error(f"Discovery failed for '{cluster_name}': {e}")
        result["success"] = False

    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="EKS Non-Production Discovery — Pre-update cluster state report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(parser)
    args = parser.parse_args()

    inv = load_inventory(args.inventory)
    clusters = get_clusters(inv, args.cluster, args.env)

    if not clusters:
        log.error("No clusters matched the given filters")
        sys.exit(1)

    print(f"\n{Fore.CYAN}EKS Discovery{Style.RESET_ALL}")
    print(f"  Clusters  : {len(clusters)}")
    for c in clusters:
        print(f"    - {c['name']} ({c['region']}, profile: {c.get('profile', 'default')})")
    print()

    log.info("Validating AWS profiles...")
    if not validate_profiles(clusters):
        log.error("Some AWS profiles failed authentication — fix credentials before proceeding")
        sys.exit(1)
    print()

    # Sequential discovery
    results = []
    for cluster in clusters:
        result = run_discover_for_cluster(cluster)
        results.append(result)

    any_failed = any(not r.get("success", True) for r in results)
    if any_failed:
        log.error(f"{Fore.RED}Some clusters failed discovery — email report not sent{Style.RESET_ALL}")
    elif args.email_to:
        send_discovery_report(
            results=results, recipients=args.email_to, sender=args.email_from,
            ses_region=args.ses_region, ses_profile=args.ses_profile, env=args.env,
        )

    if any_failed:
        log.error(f"{Fore.RED}Discovery completed with errors{Style.RESET_ALL}")
        sys.exit(1)

    log.info(f"{Fore.GREEN}Discovery complete{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
