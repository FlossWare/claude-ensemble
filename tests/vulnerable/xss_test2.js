// XSS Vulnerability 2: document.write with user input
function showWelcome(username) {
    document.write('<h1>Welcome ' + username + '</h1>');
}
