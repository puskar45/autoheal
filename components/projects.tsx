'use client'

import { motion } from 'framer-motion'
import { ExternalLink, Star } from 'lucide-react'
import { projects } from '@/data/projects'

const categoryColors: Record<string, string> = {
  Infrastructure: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  Observability: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
  Automation: 'text-green-400 bg-green-500/10 border-green-500/20',
  Security: 'text-red-400 bg-red-500/10 border-red-500/20',
  'CI/CD': 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  Networking: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
}

export default function Projects() {
  return (
    <section id="projects" className="py-32 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-16"
        >
          <p className="text-blue-400 text-sm font-medium tracking-widest uppercase mb-3">
            Portfolio
          </p>
          <h2 className="text-4xl md:text-5xl font-bold">
            Featured <span className="gradient-text">Projects</span>
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project, i) => (
            <motion.div
              key={project.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className={`glass glass-hover rounded-2xl p-6 flex flex-col ${
                project.highlight ? 'ring-1 ring-blue-500/20' : ''
              }`}
            >
              {/* Top row */}
              <div className="flex items-start justify-between mb-4">
                <span
                  className={`px-3 py-1 rounded-full text-xs border ${
                    categoryColors[project.category] ?? 'text-gray-400 bg-white/5 border-white/10'
                  }`}
                >
                  {project.category}
                </span>
                {project.highlight && (
                  <Star size={14} className="text-yellow-400 fill-yellow-400" />
                )}
              </div>

              <h3 className="text-xl font-bold text-white mb-3">{project.title}</h3>
              <p className="text-gray-400 text-sm leading-6 mb-4">{project.description}</p>

              {/* Details */}
              <ul className="space-y-2 mb-6 flex-1">
                {project.details.slice(0, 3).map((d) => (
                  <li key={d} className="text-gray-500 text-xs leading-5 flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">▸</span>
                    {d}
                  </li>
                ))}
              </ul>

              {/* Tech */}
              <div className="flex flex-wrap gap-2">
                {project.tech.map((t) => (
                  <span
                    key={t}
                    className="px-2 py-1 rounded-md bg-white/5 text-gray-400 text-xs border border-white/5"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
