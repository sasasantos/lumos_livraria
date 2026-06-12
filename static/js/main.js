// Lumos Livraria — main.js
document.addEventListener('DOMContentLoaded', () => {
    // Mark active nav link based on current page
    const currentPage = window.location.pathname.split('/').pop();
    document.querySelectorAll('nav a').forEach(link => {
        if (link.getAttribute('href') === currentPage) {
            link.classList.add('active');
        }
    });
});
