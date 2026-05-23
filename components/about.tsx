'use client'

import { motion } from 'framer-motion'
import { Cloud, Server, GitBranch, Shield } from 'lucide-react'

const stats = [
  { label: 'Years Experience', value: '5+' },
  { label: 'AWS Services', value: '20+' },
  { label: 'EKS Clusters Managed', value: '10+' },
  { label: 'Terraform Modules Built', value: '30+' },
]

const pillars = [
  {
    icon: Cloud,
    title: 'Cloud Architecture',
    desc: 'Designing scalable, secure, and cost-optimized AWS infrastructure across multi-account environments.',
  },
  {
    icon: Server,
    title: 'Kubernetes Platforms',
    desc: 'Building and operating production EKS clusters with autoscaling, GitOps, and full observability.',
  },
  {
    icon: GitBranch,
    title: 'Automation & IaC',
    desc: 'Codifying infrastructure with Terraform and automating workflows with Python, Bash, and CI/CD pipelines.',
  },
  {
    icon: Shield,
    title: 'Reliability & Security',
    desc: 'Enforcing governance policies, WAF rules, RBAC, and SLO-driven reliability practices.',
  },
]

export default function About() {
  return (
    <section id="about" className="py-32 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <p className="text-blue-400 text-sm font-medium tracking-widest uppercase mb-3">About Me</p>
          <h2 className="text-4xl md:text-5xl font-bold mb-16">
            Platform engineer who{' '}
            <span className="gradient-text">ships infrastructure</span>
          </h2>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-16 items-start mb-20">
          {/* Bio */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="space-y-5 text-gray-400 leading-8 text-lg"
          >
            <p>
              I&apos;m a Senior Platform Engineer with 5+ years of experience designing, automating,
              and operating cloud-native infrastructure on AWS. My work sits at the intersection of
              infrastructure engineering, developer experience, and production reliability.
            </p>
            <p>
              I specialize in Kubernetes (EKS), Terraform, GitOps with ArgoCD, and building
              observability platforms that give engineering teams full visibility into their systems.
              I&apos;ve managed multi-environment EKS clusters, built reusable Terraform module
              libraries, and automated complex operational workflows using Python and Jenkins.
            </p>
            <p>
              I care deeply about reducing toil, improving developer productivity, and building
              platforms that teams actually enjoy using. When infrastructure is invisible and
              deployments are boring — that&apos;s when I know the job is done right.
            </p>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="grid grid-cols-2 gap-4"
          >
            {stats.map((s) => (
              <div key={s.label} className="glass rounded-2xl p-6 text-center glow-blue">
                <div className="text-4xl font-black gradient-text mb-2">{s.value}</div>
                <div className="text-gray-400 text-sm">{s.label}</div>
              </div>
            ))}
          </motion.div>
        </div>

        {/* Pillars */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {pillars.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="glass glass-hover rounded-2xl p-6"
            >
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center mb-4">
                <p.icon size={20} className="text-blue-400" />
              </div>
              <h3 className="font-semibold text-white mb-2">{p.title}</h3>
              <p className="text-gray-500 text-sm leading-6">{p.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
