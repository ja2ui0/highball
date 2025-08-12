// Navigation component - loads automatically on every page
document.addEventListener('DOMContentLoaded', function() {
    const navHTML = `
        <nav class="nav">
            <img src="/favicon.ico" alt="Highball" class="nav-logo">
            <a href="/">Highball</a>
            <a href="/add-job">Add Job</a>
            <a href="/config">Config</a>
            <a href="/logs">Inspect</a>
        </nav>
    `;
    
    // Find the navigation placeholder and replace it
    const navContainer = document.getElementById('navigation');
    if (navContainer) {
        navContainer.innerHTML = navHTML;
    }
});
