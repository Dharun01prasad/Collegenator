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

document.querySelector(".image-section").innerHTML = `<img class="result-image" src="/frontend/images/Results/${name}.jpg" alt="To attach your photo, Mail us @ dharun0110prasad@gmail.com or jaysuriya077@gmail.com">`
