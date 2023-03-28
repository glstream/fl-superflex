function toggleTheme() {
    const html = document.documentElement;
    const body = document.body;

    if (body.classList.contains('light-theme')) {
        html.classList.remove('light-theme');
        html.classList.add('dark-theme');
        body.classList.remove('light-theme');
        body.classList.add('dark-theme');
        localStorage.setItem('theme', 'dark');
    } else {
        html.classList.remove('dark-theme');
        html.classList.add('light-theme');
        body.classList.remove('dark-theme');
        body.classList.add('light-theme');
        localStorage.setItem('theme', 'light');
    }
}

function applyTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.className = savedTheme + '-theme';
}

document.addEventListener('DOMContentLoaded', function () {
    applyTheme();
    document.getElementById('toggleThemeBtn').addEventListener('click', toggleTheme);
});
