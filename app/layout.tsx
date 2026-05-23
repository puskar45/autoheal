import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Puskar Khadka | Senior Platform Engineer',
  description:
    'Senior Platform Engineer specializing in AWS cloud infrastructure, Kubernetes, Terraform, GitOps, and production-grade DevOps automation.',
  keywords: [
    'Platform Engineer',
    'AWS',
    'Kubernetes',
    'Terraform',
    'DevOps',
    'EKS',
    'GitOps',
    'ArgoCD',
    'Observability',
  ],
  authors: [{ name: 'Puskar Khadka' }],
  openGraph: {
    title: 'Puskar Khadka | Senior Platform Engineer',
    description:
      'Senior Platform Engineer specializing in AWS, Kubernetes, Terraform and DevOps automation.',
    type: 'website',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
