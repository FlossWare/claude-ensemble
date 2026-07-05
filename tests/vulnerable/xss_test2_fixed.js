// XSS Fixed 2: Use createElement and textContent instead of document.write
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showWelcome(username) {
    // Safe: Create elements and use textContent
    const h1 = document.createElement('h1');
    h1.textContent = 'Welcome ' + username;
    document.body.appendChild(h1);

    // Alternative: Escape before using innerHTML
    // document.body.innerHTML += '<h1>Welcome ' + escapeHtml(username) + '</h1>';
}
