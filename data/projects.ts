export type Project = {
  title: string
  description: string
  details: string[]
  tech: string[]
  category: string
  highlight?: boolean
}

export const projects: Project[] = [
  {
    title: 'Production EKS Platform',
    description:
      'End-to-end production-grade EKS infrastructure with multi-account AWS setup, autoscaling, and GitOps delivery.',
    details: [
      'Multi-environment EKS clusters (dev, staging, prod) across separate AWS accounts',
      'Karpenter-based node autoscaling with spot instance optimization',
      'Reusable Terraform modules for all AWS resources',
      'ArgoCD-based GitOps with app-of-apps pattern',
      'Automated EKS version upgrade pipeline with validation gates',
    ],
    tech: ['AWS', 'EKS', 'Terraform', 'ArgoCD', 'Karpenter', 'Python'],
    category: 'Infrastructure',
    highlight: true,
  },
  {
    title: 'Centralized Observability Stack',
    description:
      'Full-stack observability platform covering metrics, logs, and alerting for Kubernetes workloads.',
    details: [
      'Prometheus + Alertmanager for metrics collection and alerting',
      'Grafana dashboards for cluster, node, and application metrics',
      'Fluent Bit DaemonSet for log shipping to OpenSearch',
      'Custom alert rules for SLO breach detection',
      'CloudWatch integration for AWS-native service metrics',
    ],
    tech: ['Prometheus', 'Grafana', 'Fluent Bit', 'OpenSearch', 'CloudWatch', 'Alertmanager'],
    category: 'Observability',
    highlight: true,
  },
  {
    title: 'EKS Upgrade Automation',
    description:
      'Python-based automation framework for safe, zero-downtime EKS cluster version upgrades.',
    details: [
      'Automated discovery of clusters requiring upgrades via AWS API',
      'Pre-upgrade validation checks for node health and workload readiness',
      'Sequential upgrade of control plane, managed node groups, and add-ons',
      'Jenkins pipeline integration with approval gates for production',
      'Post-upgrade validation and rollback capability',
    ],
    tech: ['Python', 'AWS EKS', 'Jenkins', 'Boto3', 'Bash'],
    category: 'Automation',
    highlight: true,
  },
  {
    title: 'Kubernetes Governance Platform',
    description:
      'Policy enforcement and governance framework for multi-tenant Kubernetes clusters.',
    details: [
      'OPA/Gatekeeper policies for resource limits, image registries, and labels',
      'RBAC templates for team-based namespace isolation',
      'Automated namespace provisioning with quota enforcement',
      'Audit logging and compliance reporting',
    ],
    tech: ['Kubernetes', 'OPA', 'Gatekeeper', 'Helm', 'Python', 'RBAC'],
    category: 'Security',
  },
  {
    title: 'CI/CD Automation Platform',
    description:
      'Standardized CI/CD pipelines for containerized microservices with automated testing and deployment.',
    details: [
      'Shared Jenkins library for reusable pipeline stages',
      'Docker multi-stage builds with vulnerability scanning',
      'Automated deployment to Kubernetes via ArgoCD sync',
      'Environment promotion workflow with manual approval gates',
    ],
    tech: ['Jenkins', 'Docker', 'GitHub Actions', 'ArgoCD', 'Kubernetes'],
    category: 'CI/CD',
  },
  {
    title: 'AWS WAF & ALB Configuration',
    description:
      'Production WAF rule sets and ALB configurations for secure, highly available traffic routing.',
    details: [
      'AWS WAF managed rule groups with custom rate limiting rules',
      'ALB listener rules for path-based and host-based routing',
      'ACM certificate management and automatic renewal',
      'Route53 health checks and failover routing policies',
    ],
    tech: ['AWS WAF', 'ALB', 'Route53', 'ACM', 'CloudFront', 'Terraform'],
    category: 'Networking',
  },
]
