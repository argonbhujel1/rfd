// Ratuwamai Food Delivery — Main JS

document.addEventListener('DOMContentLoaded', () => {
  // Mobile hamburger
  const hamburger = document.getElementById('hamburger');
  const navLinks = document.getElementById('navLinks');
  if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
      navLinks.classList.toggle('open');
    });
  }

  // Auto-hide flash messages
  setTimeout(() => {
    document.querySelectorAll('.alert').forEach(el => {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    });
  }, 4500);
});

function showToast(msg, duration = 2500) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

function updateCartCount(count) {
  const el = document.getElementById('cartCount');
  if (el) el.textContent = count;
  document.querySelectorAll('.bottom-nav .badge').forEach(b => {
    if (count > 0) {
      b.textContent = count;
      b.style.display = '';
    } else {
      b.style.display = 'none';
    }
  });
}
