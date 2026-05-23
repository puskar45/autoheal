'use client'

import { motion } from 'framer-motion'
import { ArrowDown, Github, Linkedin, Mail } from 'lucide-react'

export default function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center px-6 grid-bg overflow-hidden">
      {/* Background blobs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl animate-pulse-slow pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-purple-600/10 rounded-full blur-3xl animate-pulse-slow pointer-events-none" />

      <div className="relative max-w-5xl w-full text-center">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass text-sm text-blue-400 mb-8"
        >
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          Available for opportunities
        </motion.div>

        {/* Name */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="text-6xl md:text-8xl font-black mb-4 tracking-tight leading-none"
        >
          Puskar{' '}
          <span className="gradient-text">Khadka</span>
        </motion.h1>

        {/* Title */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-2xl md:text-3xl font-light text-gray-400 mb-6"
        >
          Senior Platform Engineer
        </motion.p>

        {/* Tagline */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-lg text-gray-500 max-w-2xl mx-auto leading-relaxed mb-10"
        >
          Building production-grade cloud infrastructure on AWS — Kubernetes platforms,
          Terraform automation, GitOps pipelines, and observability systems at scale.
        </motion.p>

        {/* Tech pills */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="flex flex-wrap justify-center gap-2 mb-12"
        >
          {['AWS', 'Kubernetes', 'Terraform', 'ArgoCD', 'Python', 'Prometheus'].map((t) => (
            <span
              key={t}
              className="px-3 py-1 rounded-full text-xs glass text-gray-300 border border-white/10"
            >
              {t}
            </span>
          ))}
        </motion.div>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="flex flex-wrap gap-4 justify-center mb-16"
        >
          <a
            href="#projects"
            className="px-8 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 transition font-medium text-white shadow-lg shadow-blue-500/20"
          >
            View Projects
          </a>
          <a
            href="#contact"
            className="px-8 py-3 rounded-xl glass hover:bg-white/10 transition font-medium border border-white/10"
          >
            Get in Touch
          </a>
          <a
            href="/resume.pdf"
            className="px-8 py-3 rounded-xl glass hover:bg-white/10 transition font-medium border border-white/10"
          >
            Download Resume
          </a>
        </motion.div>

        {/* Social icons */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9 }}
          className="flex justify-center gap-4"
        >
          {[
            { icon: Github, href: 'https://github.com/puskarkhadka', label: 'GitHub' },
            { icon: Linkedin, href: 'https://linkedin.com/in/puskarkhadka', label: 'LinkedIn' },
            { icon: Mail, href: 'mailto:puskar@example.com', label: 'Email' },
          ].map(({ icon: Icon, href, label }) => (
            <a
              key={label}
              href={href}
              aria-label={label}
              className="p-3 glass rounded-xl hover:bg-white/10 hover:scale-110 transition text-gray-400 hover:text-white"
            >
              <Icon size={20} />
            </a>
          ))}
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2 }}
        className="absolute bottom-10 left-1/2 -translate-x-1/2 text-gray-600 flex flex-col items-center gap-2"
      >
        <span className="text-xs tracking-widest uppercase">Scroll</span>
        <ArrowDown size={16} className="animate-bounce" />
      </motion.div>
    </section>
  )
}
