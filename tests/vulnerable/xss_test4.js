// XSS Vulnerability 4: URL parameter in innerHTML
function showUrlParam() {
    const urlParams = new URLSearchParams(window.location.search);
    const content = urlParams.get('content');
    document.getElementById('output').innerHTML = content;
}
