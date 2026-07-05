// XSS Fixed 3: Use textContent for user input
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function renderMessage(msg) {
    const div = document.createElement('div');
    const p = document.createElement('p');

    // Safe: textContent doesn't parse HTML
    p.textContent = msg;
    div.appendChild(p);
    document.body.appendChild(div);

    // Alternative: Escape before using innerHTML
    // div.innerHTML = '<p>' + escapeHtml(msg) + '</p>';
}
