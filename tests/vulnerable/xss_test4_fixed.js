// XSS Fixed 4: Sanitize URL parameters before display
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showUrlParam() {
    const urlParams = new URLSearchParams(window.location.search);
    const content = urlParams.get('content');

    // Safe: textContent doesn't parse HTML
    document.getElementById('output').textContent = content;

    // Alternative: Escape before using innerHTML
    // document.getElementById('output').innerHTML = escapeHtml(content);
}
