// XSS Vulnerability 5: Template string in innerHTML
function displayTemplate(data) {
    const html = `<div class="item">${data.name}</div>`;
    document.getElementById('container').innerHTML += html;
}
