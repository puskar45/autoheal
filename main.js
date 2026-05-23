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

// Contact form
function submitForm(e) {
  e.preventDefault()
  const name = document.getElementById('form-name').value
  const email = document.getElementById('form-email').value
  const message = document.getElementById('form-message').value
  const resume = document.getElementById('form-resume').checked

  const subject = resume ? 'Resume Request & Message from ' + name : 'Message from ' + name
  const body = `Name: ${name}\nEmail: ${email}\n\n${message}${resume ? '\n\n[This person has requested a copy of your CV/Resume]' : ''}`

  window.location.href = `mailto:puskarkhadka45@gmail.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

// Request resume — scroll to form and check the resume checkbox
function requestResume() {
  setTimeout(() => {
    document.getElementById('contact').scrollIntoView({ behavior: 'smooth' })
    const checkbox = document.getElementById('form-resume')
    if (checkbox) checkbox.checked = true
  }, 50)
}
