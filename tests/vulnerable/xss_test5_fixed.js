// XSS Fixed 5: Escape template data before rendering
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function displayTemplate(data) {
    // Safe: Escape user data
    const safeN = escapeHtml(data.name);
    const html = `<div class="item">${safeName}</div>`;
    document.getElementById('container').innerHTML += html;

    // Better: Use DOM API
    // const div = document.createElement('div');
    // div.className = 'item';
    // div.textContent = data.name;
    // document.getElementById('container').appendChild(div);
}
