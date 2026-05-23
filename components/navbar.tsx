'use client'

import { useState, useEffect } from 'react'
import { Menu, X } from 'lucide-react'

const links = [
  { label: 'About', href: '#about' },
  { label: 'Skills', href: '#skills' },
  { label: 'Experience', href: '#experience' },
  { label: 'Projects', href: '#projects' },
  { label: 'Contact', href: '#contact' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? 'glass shadow-lg shadow-black/20' : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
        <a href="#" className="font-bold text-xl gradient-text tracking-tight">
          Puskar Khadka
        </a>

        {/* Desktop */}
        <div className="hidden md:flex items-center gap-8 text-sm text-gray-300">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="hover:text-white hover:text-blue-400 transition-colors duration-200"
            >
              {l.label}
            </a>
          ))}
          <a
            href="/resume.pdf"
            className="px-4 py-2 rounded-lg border border-blue-500/40 text-blue-400 hover:bg-blue-500/10 transition text-sm"
          >
            Resume
          </a>
        </div>

        {/* Mobile toggle */}
        <button
          className="md:hidden text-gray-300"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden glass border-t border-white/10 px-6 py-4 flex flex-col gap-4 text-sm text-gray-300">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="hover:text-white transition"
            >
              {l.label}
            </a>
          ))}
          <a href="/resume.pdf" className="text-blue-400">
            Resume ↗
          </a>
        </div>
      )}
    </nav>
  )
}
