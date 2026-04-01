#!/usr/bin/env python3
from __future__ import annotations
"""
EKS Non-Production Post-Update Validation.

Usage:
  python validate.py                                          # Validate all nonprod clusters
  python validate.py --cluster eks-cap-dev-datawing            # Single cluster
  python validate.py --email-to team@co.com                    # Validate + email report
"""

import argparse
import sys
from datetime import datetime, timezone

from eks_utils import (
    Fore, Style, log,
    load_inventory, get_clusters, get_eks_client, validate_profiles,
    discover_nodegroups, discover_addons, get_cluster_version,
    get_nodegroup_info, get_addon_info, get_latest_addon_version,
    validate_nodes, validate_pods, get_eks_insights,
    _run_kubectl, _send_ses_email, add_common_args,
)

import json
import boto3


# ─── Validation logic ────────────────────────────────────────────────────────

def validate_cluster(cluster: dict, client) -> tuple[bool, list[dict]]:
    """Run all post-upgrade validations for a cluster."""
    cluster_name = cluster["name"]
    region = cluster["region"]
    profile = cluster.get("profile", "default")

    log.info(f"{Fore.YELLOW}── Post-Upgrade Validation ──{Style.RESET_ALL}")
    all_checks = []
    all_ok = True

    # 1. Cluster version
    log.info("  Checking cluster version...")
    version = get_cluster_version(client, cluster_name)
    log.info(f"  Cluster version: {version}")
    all_checks.append({"check": "cluster_version", "version": version})

    # 2. Addon health + versions + latest version check
    log.info("  Checking addon health and versions...")
    addons = discover_addons(client, cluster_name)
    for addon in addons:
        info = get_addon_info(client, cluster_name, addon)
        status = info["status"]
        addon_version = info.get("addonVersion", "?")
        healthy = status == "ACTIVE"
        latest = get_latest_addon_version(client, addon, version)
        on_latest = bool(latest and addon_version == latest)
        if not healthy:
            all_ok = False
        icon = "✓" if healthy else "✗"
        if on_latest:
            log.info(f"  {icon} Addon '{addon}': {addon_version} ({status}) — on latest")
        else:
            log.warning(f"  {icon} Addon '{addon}': {addon_version} ({status}) — NOT on latest (latest: {latest or '?'})")
        all_checks.append({
            "check": "addon", "name": addon,
            "status": status, "version": addon_version,
            "latest": latest or "?", "on_latest": on_latest,
        })

    # 3. Node readiness + kubelet version check via kubectl
    log.info("  Checking node readiness and kubelet versions...")
    ok, node_results = validate_nodes(cluster_name, region, profile)
    all_checks.extend(node_results)
    if not ok:
        all_ok = False

    # Check each node's kubelet version matches cluster version
    log.info("  Checking node AMI/kubelet versions...")
    ok_kubectl, output = _run_kubectl(cluster_name, region, profile,
                                       ["get", "nodes", "-o", "json"])
    if ok_kubectl:
        try:
            nodes_data = json.loads(output)
            for node in nodes_data.get("items", []):
                node_name = node["metadata"]["name"]
                node_info = node.get("status", {}).get("nodeInfo", {})
                kubelet_ver = node_info.get("kubeletVersion", "?")
                os_image = node_info.get("osImage", "?")
                # kubelet version looks like "v1.34.1-eks-abcdef" — extract major.minor
                kubelet_minor = ".".join(kubelet_ver.lstrip("v").split(".")[:2]) if kubelet_ver != "?" else "?"
                on_latest_kubelet = kubelet_minor == version
                if on_latest_kubelet:
                    log.info(f"  ✓ Node '{node_name}': kubelet={kubelet_ver}, os={os_image} — matches cluster version")
                else:
                    log.warning(f"  ✗ Node '{node_name}': kubelet={kubelet_ver}, os={os_image} — expected k8s {version}")
                all_checks.append({
                    "check": "node_version", "name": node_name,
                    "kubelet_version": kubelet_ver, "os_image": os_image,
                    "on_latest": on_latest_kubelet,
                })
        except json.JSONDecodeError:
            log.warning("  Could not parse node JSON for version check")
    else:
        log.warning(f"  Could not get node details for version check: {output}")

    # 4. Node group AMI versions + latest version check via SSM
    log.info("  Checking node group versions...")
    nodegroups = discover_nodegroups(client, cluster_name)
    for ng in nodegroups:
        info = get_nodegroup_info(client, cluster_name, ng)
        release = info.get("releaseVersion", "?")
        ng_version = info.get("version", "?")
        ng_status = info["status"]
        ami_type = info.get("amiType", "?")
        healthy = ng_status == "ACTIVE"
        if not healthy:
            all_ok = False

        # Check latest AMI via SSM
        ami_ssm_configs = {
            "AL2_x86_64":              f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2/recommended/release_version",
            "AL2_x86_64_GPU":          f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2-gpu/recommended/release_version",
            "AL2_ARM_64":              f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2-arm64/recommended/release_version",
            "AL2023_x86_64_STANDARD":  f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2023/x86_64/standard/recommended/release_version",
            "AL2023_ARM_64_STANDARD":  f"/aws/service/eks/optimized-ami/{version}/amazon-linux-2023/arm64/standard/recommended/release_version",
            "BOTTLEROCKET_x86_64":     f"/aws/service/bottlerocket/aws-k8s-{version}/x86_64/latest/image_version",
            "BOTTLEROCKET_ARM_64":     f"/aws/service/bottlerocket/aws-k8s-{version}/arm64/latest/image_version",
        }
        latest_release = None
        on_latest = True
        ssm_path = ami_ssm_configs.get(ami_type)
        if ssm_path:
            try:
                session_kwargs = {"region_name": region}
                p = cluster.get("profile")
                if p:
                    session_kwargs["profile_name"] = p
                ssm = boto3.Session(**session_kwargs).client("ssm")
                latest_release = ssm.get_parameter(Name=ssm_path)["Parameter"]["Value"]
                current_comparable = release.split("-")[0] if release else ""
                latest_comparable = latest_release.split("-")[0] if latest_release else ""
                if current_comparable != latest_comparable:
                    on_latest = False
                elif release.strip() != latest_release.strip():
                    on_latest = False
            except Exception as e:
                log.warning(f"  SSM lookup failed for '{ng}': {e}")

        icon = "✓" if healthy else "✗"
        if on_latest:
            log.info(f"  {icon} Node group '{ng}': k8s={ng_version}, AMI={ami_type}, release={release} ({ng_status}) — on latest")
        else:
            log.warning(f"  {icon} Node group '{ng}': k8s={ng_version}, AMI={ami_type}, release={release} ({ng_status}) — NOT on latest (latest: {latest_release or '?'})")
        all_checks.append({
            "check": "nodegroup", "name": ng,
            "status": ng_status, "version": ng_version,
            "release": release, "ami_type": ami_type,
            "latest_release": latest_release, "on_latest": on_latest,
        })

    # 5. Pod health across all namespaces via kubectl
    log.info("  Checking pod health...")
    ok, pod_results = validate_pods(cluster_name, region, profile)
    all_checks.extend(pod_results)
    if not ok:
        all_ok = False

    # 6. EKS Insights
    log.info("  Checking EKS insights...")
    insights = get_eks_insights(client, cluster_name)
    failing_insights = [i for i in insights if i.get("status") != "PASSING"]
    if failing_insights:
        all_ok = False
        for ins in failing_insights:
            log.warning(f"  ⚠ [{ins['category']}] {ins['name']} — {ins['status']}")
    else:
        log.info(f"  ✓ All insights passing ({len(insights)})")
    all_checks.append({
        "check": "insights",
        "total": len(insights),
        "failing": len(failing_insights),
        "details": failing_insights,
    })

    if all_ok:
        log.info(f"  {Fore.GREEN}✓ All validations passed{Style.RESET_ALL}")
    else:
        log.error(f"  {Fore.RED}✗ Some validations failed{Style.RESET_ALL}")

    return all_ok, all_checks


# ─── Validation report ────────────────────────────────────────────────────────

def build_validation_report(results: list[dict], env: str = "NonProd") -> tuple[str, str]:
    """Build an HTML post-upgrade validation report."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date_str = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    total = len(results)
    failed = sum(1 for r in results if not r["success"])

    subject = f"EKS {env} Post-Update Validation - {date_str}"

    th = 'style="padding:6px 10px;text-align:left;"'
    td = 'style="padding:6px 10px;border-top:1px solid #eee;"'

    cluster_rows = []
    for r in results:
        checks = r.get("validation", [])
        cluster_name = r["cluster"]
        cluster_icon = "✅" if r["success"] else "⚠"
        cluster_color = "#28a745" if r["success"] else "#dc3545"

        # Cluster version
        cv = next((c for c in checks if c.get("check") == "cluster_version"), None)
        version_html = f'k8s {cv["version"]}' if cv else "?"

        # Addons table
        addon_checks = [c for c in checks if c.get("check") == "addon"]
        addon_rows = []
        for a in addon_checks:
            ver = a.get("version", "?")
            latest = a.get("latest", "?")
            on_latest = a.get("on_latest", True)
            status_ok = a["status"] == "ACTIVE"
            status_color = "#28a745" if status_ok else "#dc3545"
            ver_color = "#28a745" if on_latest else "#dc3545"
            latest_badge = f'<span style="color:#28a745;">✓ Yes</span>' if on_latest else f'<span style="color:#dc3545;">✗ No</span>'
            addon_rows.append(
                f'<tr><td {td}>{a["name"]}</td>'
                f'<td {td}>{ver}</td>'
                f'<td {td}>{latest}</td>'
                f'<td {td}>{latest_badge}</td>'
                f'<td {td}><span style="color:{status_color};">{a["status"]}</span></td></tr>'
            )
        addon_table = f"""
          <table style="width:100%;border-collapse:collapse;margin:6px 0;">
            <tr style="background:#f5f5f5;">
              <th {th}>Addon</th><th {th}>Current</th><th {th}>Latest</th><th {th}>On Latest</th><th {th}>Status</th>
            </tr>
            {''.join(addon_rows) if addon_rows else f'<tr><td colspan="5" {td} style="color:#888;">None</td></tr>'}
          </table>"""

        # Node groups table
        ng_checks = [c for c in checks if c.get("check") == "nodegroup"]
        ng_rows = []
        for ng in ng_checks:
            release = ng.get("release", "?")
            latest_rel = ng.get("latest_release", "?") or "?"
            on_latest = ng.get("on_latest", True)
            status_ok = ng["status"] == "ACTIVE"
            status_color = "#28a745" if status_ok else "#dc3545"
            latest_badge = f'<span style="color:#28a745;">✓ Yes</span>' if on_latest else f'<span style="color:#dc3545;">✗ No</span>'
            ng_rows.append(
                f'<tr><td {td}>{ng["name"]}</td>'
                f'<td {td}>{ng.get("ami_type", "?")}</td>'
                f'<td {td}>{release}</td>'
                f'<td {td}>{latest_rel}</td>'
                f'<td {td}>{latest_badge}</td>'
                f'<td {td}><span style="color:{status_color};">{ng["status"]}</span></td></tr>'
            )
        ng_table = f"""
          <table style="width:100%;border-collapse:collapse;margin:6px 0;">
            <tr style="background:#f5f5f5;">
              <th {th}>Node Group</th><th {th}>AMI Type</th><th {th}>Current</th><th {th}>Latest</th><th {th}>On Latest</th><th {th}>Status</th>
            </tr>
            {''.join(ng_rows) if ng_rows else f'<tr><td colspan="6" {td} style="color:#888;">None</td></tr>'}
          </table>"""

        # Nodes table — readiness + kubelet version + OS image
        node_checks = [c for c in checks if c.get("check") == "node"]
        node_ver_checks = [c for c in checks if c.get("check") == "node_version"]
        # Build a lookup of node version info by name
        node_ver_map = {c["name"]: c for c in node_ver_checks}
        node_rows_html = []
        for n in node_checks:
            name = n["name"]
            ready = n["status"] == "ready"
            ready_color = "#28a745" if ready else "#dc3545"
            ready_text = "Ready" if ready else n["status"]
            ver_info = node_ver_map.get(name, {})
            kubelet = ver_info.get("kubelet_version", "?")
            os_img = ver_info.get("os_image", "?")
            on_latest = ver_info.get("on_latest", True)
            latest_badge = f'<span style="color:#28a745;">✓ Yes</span>' if on_latest else f'<span style="color:#dc3545;">✗ No</span>'
            node_rows_html.append(
                f'<tr><td {td}>{name}</td>'
                f'<td {td}><span style="color:{ready_color};">{ready_text}</span></td>'
                f'<td {td}>{kubelet}</td>'
                f'<td {td}>{os_img}</td>'
                f'<td {td}>{latest_badge}</td></tr>'
            )
        node_table = f"""
          <table style="width:100%;border-collapse:collapse;margin:6px 0;">
            <tr style="background:#f5f5f5;">
              <th {th}>Node</th><th {th}>Status</th><th {th}>Kubelet</th><th {th}>OS Image</th><th {th}>On Latest</th>
            </tr>
            {''.join(node_rows_html) if node_rows_html else f'<tr><td colspan="5" {td} style="color:#888;">None</td></tr>'}
          </table>"""

        # Pods
        pod_checks = [c for c in checks if c.get("check") == "pods"]
        total_healthy = sum(p.get("healthy", 0) for p in pod_checks)
        all_unhealthy = []
        for p in pod_checks:
            ns = p.get("namespace", "")
            for pod in p.get("unhealthy_pods", []):
                all_unhealthy.append(f"{ns}/{pod}")
        if all_unhealthy:
            pod_html = f'<span style="color:#dc3545;">⚠ {len(all_unhealthy)} unhealthy pod(s):</span><br>'
            pod_html += '<br>'.join(f'&nbsp;&nbsp;⚠ {p}' for p in all_unhealthy)
        else:
            pod_html = f'<span style="color:#28a745;">✓ All pods healthy ({total_healthy})</span>'

        # EKS Insights
        insight_check = next((c for c in checks if c.get("check") == "insights"), None)
        if insight_check:
            failing = insight_check.get("details", [])
            total_insights = insight_check.get("total", 0)
            if failing:
                insight_lines = []
                for ins in failing:
                    line = f'<span style="color:#dc3545;">⚠ [{ins.get("category","")}] {ins.get("name","")} — {ins["status"]}</span>'
                    if ins.get("description"):
                        line += f'<br><small style="color:#666;">{ins["description"][:200]}</small>'
                    if ins.get("recommendation"):
                        line += f'<br><small style="color:#0066cc;">Recommendation: {ins["recommendation"][:200]}</small>'
                    insight_lines.append(line)
                insight_html = '<br>'.join(insight_lines)
            else:
                insight_html = f'<span style="color:#28a745;">✓ All insights passing ({total_insights})</span>'
        else:
            insight_html = '<span style="color:#888;">No insight data</span>'

        cluster_rows.append(f"""
        <tr><td colspan="2" style="background:#232f3e;color:white;padding:10px;font-weight:bold;">
          <span style="color:{cluster_color};">{cluster_icon}</span> {cluster_name}
          &nbsp;<small style="color:#aaa;">{r['region']} &middot; {r['profile']} &middot; {version_html}</small>
        </td></tr>
        <tr><td colspan="2" style="padding:12px;">
          <b>Addons</b>{addon_table}<br>
          <b>Node Groups</b>{ng_table}<br>
          <b>Nodes</b>{node_table}<br>
          <b>Pods:</b> {pod_html}<br><br>
          <b>EKS Insights:</b><br>{insight_html}
        </td></tr>""")

    html = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#333;max-width:900px;margin:0 auto;padding:20px;">
      <h2 style="color:#232f3e;">EKS Post-Update Validation</h2>
      <table style="margin-bottom:20px;">
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Timestamp:</td><td>{timestamp}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Clusters:</td><td>{total}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Result:</td>
            <td style="color:{'#dc3545' if failed else '#28a745'};font-weight:bold;">
            {total - failed}/{total} healthy, {failed} with issues</td></tr>
      </table>
      <table style="width:100%;border-collapse:collapse;border:1px solid #ddd;">
        {''.join(cluster_rows)}
      </table>
      <p style="color:#888;font-size:12px;margin-top:20px;">Generated by EKS Upgrade Automation — Validation Mode</p>
    </body>
    </html>"""
    return subject, html


def send_validation_report(results: list[dict], recipients: list[str], sender: str,
                            ses_region: str, ses_profile: str | None, env: str = "NonProd"):
    subject, html_body = build_validation_report(results, env)
    _send_ses_email(subject, html_body, recipients, sender, ses_region, ses_profile)


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def run_validate_for_cluster(cluster: dict) -> dict:
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
        "validation": [],
    }

    try:
        client = get_eks_client(cluster)
        ok, checks = validate_cluster(cluster, client)
        result["validation"] = checks
        if not ok:
            result["success"] = False
    except Exception as e:
        log.error(f"Validation failed for '{cluster_name}': {e}")
        result["success"] = False

    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="EKS Non-Production Post-Update Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(parser)
    args = parser.parse_args()

    inv = load_inventory(args.inventory)
    clusters = get_clusters(inv, args.cluster, args.env)

    if not clusters:
        log.error("No clusters matched the given filters")
        sys.exit(1)

    print(f"\n{Fore.CYAN}EKS Post-Update Validation{Style.RESET_ALL}")
    print(f"  Clusters  : {len(clusters)}")
    for c in clusters:
        print(f"    - {c['name']} ({c['region']}, profile: {c.get('profile', 'default')})")
    print()

    log.info("Validating AWS profiles...")
    if not validate_profiles(clusters):
        log.error("Some AWS profiles failed authentication — fix credentials before proceeding")
        sys.exit(1)
    print()

    # Sequential validation
    results = []
    for cluster in clusters:
        result = run_validate_for_cluster(cluster)
        results.append(result)

    # Summary
    print(f"\n{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  VALIDATION SUMMARY{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
    for r in results:
        status = f"{Fore.GREEN}✓ HEALTHY{Style.RESET_ALL}" if r["success"] else f"{Fore.RED}✗ ISSUES{Style.RESET_ALL}"
        print(f"  {r['cluster']}: {status}")

    if args.email_to:
        send_validation_report(
            results=results, recipients=args.email_to, sender=args.email_from,
            ses_region=args.ses_region, ses_profile=args.ses_profile, env=args.env,
        )

    any_failed = any(not r["success"] for r in results)
    if any_failed:
        log.error(f"{Fore.RED}Some clusters have issues{Style.RESET_ALL}")
        sys.exit(1)
    log.info(f"{Fore.GREEN}All clusters healthy{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
