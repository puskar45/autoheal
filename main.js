// Navbar scroll effect
window.addEventListener('scroll', () => {
  document.getElementById('navbar').classList.toggle('scrolled', window.scrollY > 20)
})

// Mobile menu toggle
function toggleMenu() {
  document.getElementById('mobileMenu').classList.toggle('open')
}

// Scroll animations
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => entry.target.classList.add('visible'), i * 80)
      observer.unobserve(entry.target)
    }
  })
}, { threshold: 0.1 })

document.querySelectorAll('.fade-up').forEach(el => observer.observe(el))
