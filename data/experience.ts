export type Experience = {
  role: string
  company: string
  location: string
  duration: string
  type: string
  highlights: string[]
  tech: string[]
}

export const experiences: Experience[] = [
  {
    role: 'Senior Platform Engineer',
    company: 'Current Company',
    location: 'Remote',
    duration: '2024 – Present',
    type: 'Full-time',
    highlights: [
      'Designed and maintained production-grade EKS clusters across multiple AWS accounts and environments',
      'Built reusable Terraform modules for VPC, EKS, RDS, ALB, and IAM — reducing provisioning time by 60%',
      'Implemented GitOps workflows using ArgoCD for automated, auditable Kubernetes deployments',
      'Deployed centralized observability stack: Prometheus, Grafana, Fluent Bit, and OpenSearch',
      'Automated EKS version upgrades across non-prod and prod clusters using Python and Jenkins',
      'Enforced Kubernetes governance policies using OPA/Gatekeeper and RBAC controls',
      'Managed WAF rules, ALB configurations, and Route53 DNS for production traffic routing',
    ],
    tech: ['AWS', 'EKS', 'Terraform', 'ArgoCD', 'Prometheus', 'Grafana', 'Jenkins', 'Python'],
  },
  {
    role: 'Cloud / DevOps Engineer',
    company: 'Previous Company',
    location: 'Remote',
    duration: '2021 – 2024',
    type: 'Full-time',
    highlights: [
      'Built and maintained CI/CD pipelines using Jenkins and GitHub Actions for containerized microservices',
      'Containerized legacy applications using Docker and migrated workloads to Kubernetes',
      'Provisioned AWS infrastructure using Terraform and CloudFormation templates',
      'Implemented log aggregation and monitoring using CloudWatch, Fluent Bit, and Grafana',
      'Reduced deployment failures by 40% through automated rollback and health-check pipelines',
      'Collaborated with development teams to define SLOs, SLIs, and error budgets',
    ],
    tech: ['AWS', 'Docker', 'Kubernetes', 'Jenkins', 'Terraform', 'CloudWatch', 'GitHub Actions'],
  },
]
