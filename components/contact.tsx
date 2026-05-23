'use client'

import { motion } from 'framer-motion'
import { Github, Linkedin, Mail, MapPin, Send } from 'lucide-react'

const socials = [
  {
    icon: Github,
    label: 'GitHub',
    value: 'github.com/puskarkhadka',
    href: 'https://github.com/puskarkhadka',
    color: 'hover:border-gray-400/40',
  },
  {
    icon: Linkedin,
    label: 'LinkedIn',
    value: 'linkedin.com/in/puskarkhadka',
    href: 'https://linkedin.com/in/puskarkhadka',
    color: 'hover:border-blue-400/40',
  },
  {
    icon: Mail,
    label: 'Email',
    value: 'puskar@example.com',
    href: 'mailto:puskar@example.com',
    color: 'hover:border-purple-400/40',
  },
]

export default function Contact() {
  return (
    <section id="contact" className="py-32 px-6">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-blue-400 text-sm font-medium tracking-widest uppercase mb-3">
            Contact
          </p>
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            Let&apos;s <span className="gradient-text">Connect</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-xl mx-auto leading-relaxed">
            Open to platform engineering roles, cloud architecture consulting, and DevOps
            collaboration. Feel free to reach out.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-4 mb-12">
          {socials.map((s, i) => (
            <motion.a
              key={s.label}
              href={s.href}
              target="_blank"
              rel="noopener noreferrer"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className={`glass rounded-2xl p-6 flex flex-col items-center gap-3 border border-white/10 transition-all duration-300 hover:scale-105 ${s.color}`}
            >
              <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center">
                <s.icon size={22} className="text-gray-300" />
              </div>
              <div className="text-center">
                <div className="font-medium text-white text-sm">{s.label}</div>
                <div className="text-gray-500 text-xs mt-1">{s.value}</div>
              </div>
            </motion.a>
          ))}
        </div>

        {/* Location note */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.4 }}
          className="flex items-center justify-center gap-2 text-gray-500 text-sm"
        >
          <MapPin size={14} />
          <span>Open to remote opportunities worldwide</span>
        </motion.div>
      </div>
    </section>
  )
}
