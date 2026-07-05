// XSS Fixed 1: Use textContent instead of innerHTML
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function displayComment(userComment) {
    // Safe: textContent doesn't parse HTML
    document.getElementById('comments').textContent = userComment;

    // Alternative: Escape HTML before using innerHTML
    // document.getElementById('comments').innerHTML = escapeHtml(userComment);
}
