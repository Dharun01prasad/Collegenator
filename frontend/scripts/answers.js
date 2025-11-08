const urlParams = new URLSearchParams(window.location.search);
const name = urlParams.get('name');

if (name) {
    document.querySelector('.character').textContent = name;
} else {
    document.querySelector('.character').textContent = "Unknown";
}

function playAgain() {
    window.location.href = '/';
}