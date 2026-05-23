export type SkillCategory = {
  label: string
  icon: string
  color: string
  items: string[]
}

export const skillCategories: SkillCategory[] = [
  {
    label: 'Cloud & AWS',
    icon: '☁️',
    color: 'from-orange-500/20 to-yellow-500/20 border-orange-500/20',
    items: ['AWS', 'EC2', 'EKS', 'RDS', 'S3', 'VPC', 'IAM', 'Route53', 'ALB', 'WAF', 'CloudFront', 'ACM'],
  },
  {
    label: 'Kubernetes & Containers',
    icon: '⚙️',
    color: 'from-blue-500/20 to-cyan-500/20 border-blue-500/20',
    items: ['Kubernetes', 'EKS', 'Helm', 'ArgoCD', 'Docker', 'Karpenter', 'Cluster Autoscaler', 'RBAC'],
  },
  {
    label: 'Infrastructure as Code',
    icon: '🏗️',
    color: 'from-purple-500/20 to-violet-500/20 border-purple-500/20',
    items: ['Terraform', 'CloudFormation', 'Terragrunt', 'Ansible', 'Bash', 'Python'],
  },
  {
    label: 'CI/CD & GitOps',
    icon: '🔄',
    color: 'from-green-500/20 to-emerald-500/20 border-green-500/20',
    items: ['Jenkins', 'GitHub Actions', 'ArgoCD', 'GitOps', 'Atlantis', 'Bitbucket Pipelines'],
  },
  {
    label: 'Observability',
    icon: '📊',
    color: 'from-pink-500/20 to-rose-500/20 border-pink-500/20',
    items: ['Prometheus', 'Grafana', 'Fluent Bit', 'OpenSearch', 'CloudWatch', 'Alertmanager', 'Loki'],
  },
  {
    label: 'Security & Networking',
    icon: '🔒',
    color: 'from-red-500/20 to-orange-500/20 border-red-500/20',
    items: ['AWS WAF', 'Security Groups', 'NACLs', 'VPN', 'TLS/SSL', 'Secrets Manager', 'KMS'],
  },
]
