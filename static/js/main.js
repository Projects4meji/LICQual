document.addEventListener('DOMContentLoaded', function () {
  // Smooth scrolling for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });

  // Mobile menu toggle
  function toggleMobileMenu() {
    const mobileMenu = document.getElementById('mobile-menu');
    const menuIcon = document.getElementById('menu-icon');
    
    if (mobileMenu.classList.contains('hidden')) {
      mobileMenu.classList.remove('hidden');
      menuIcon.classList.remove('fa-bars');
      menuIcon.classList.add('fa-times');
    } else {
      mobileMenu.classList.add('hidden');
      menuIcon.classList.remove('fa-times');
      menuIcon.classList.add('fa-bars');
    }
  }

  // Add scroll effect to navbar
  window.addEventListener('scroll', function() {
    const navbar = document.querySelector('nav');
    if (window.scrollY > 100) {
      navbar.classList.add('shadow-lg');
    } else {
      navbar.classList.remove('shadow-lg');
    }
  });

  // Debug: Log all form submissions to catch unexpected handlers
  document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      console.log('DEBUG: Form submission detected for', form.action, 'data-ajax:', form.dataset.ajax, 'Time:', new Date().toISOString());
    });
  });

  // Form submission handling (opt-in only)
  // Only intercept forms explicitly marked with data-ajax="true"
  document.querySelectorAll('form[data-ajax="true"]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      console.log('DEBUG: AJAX form submission for', form.action, 'Time:', new Date().toISOString());
      fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
        .then(response => response.json())
        .then(data => {
          console.log('DEBUG: AJAX response:', data);
          if (data.success) {
            alert('Form submitted successfully!');
          } else {
            alert('Error: ' + (data.error || 'Submission failed.'));
          }
        })
        .catch(error => {
          console.error('DEBUG: AJAX error:', error);
          alert('An error occurred while submitting the form.');
        });
    });
  });

  // Clear existing submit listeners for newsletter form to prevent multiple alerts
  const newsletterForm = document.querySelector('form[action*="email-subscription"]');
  if (newsletterForm) {
    console.log('DEBUG: Clearing existing submit listeners for newsletter form');
    const newForm = newsletterForm.cloneNode(true);
    newsletterForm.parentNode.replaceChild(newForm, newsletterForm);
  }

  // Scroll-triggered animations
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-fade-in-up');
      }
    });
  }, observerOptions);

  // Observe elements with animation classes
  const animatedElements = document.querySelectorAll('.animate-fade-in-up, .animate-fade-in-left, .animate-fade-in-right');
  animatedElements.forEach(el => {
    observer.observe(el);
  });

  // Add hover effects to cards
  const cards = document.querySelectorAll('.card-hover');
  cards.forEach(card => {
    card.addEventListener('mouseenter', function() {
      this.style.transform = 'translateY(-8px)';
      this.style.boxShadow = '0 25px 50px rgba(0, 0, 0, 0.15)';
    });
    
    card.addEventListener('mouseleave', function() {
      this.style.transform = 'translateY(0)';
      this.style.boxShadow = '';
    });
  });
});