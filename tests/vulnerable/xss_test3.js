// XSS Vulnerability 3: Direct DOM manipulation with user input
function renderMessage(msg) {
    const div = document.createElement('div');
    div.innerHTML = '<p>' + msg + '</p>';
    document.body.appendChild(div);
}
