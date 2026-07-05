// XSS Vulnerability 1: innerHTML with user input
function displayComment(userComment) {
    document.getElementById('comments').innerHTML = userComment;
}
