const question_box = document.querySelector(".question-text");
const answer_box = document.querySelector(".answer-box");
const question_number = document.querySelector(".question-number");

let questionCount = 0;

// Use relative URLs instead of hardcoded localhost
const API_BASE = window.location.origin;

function generateNewOptions(option) {
  const newButton = document.createElement("button");
  newButton.classList.add("answer-btn");
  newButton.innerText = option;
  answer_box.appendChild(newButton);
  addingEvents(newButton);
}

function generateNewQuestion(question) {
  question_box.innerHTML = question;
}

function addingEvents(button) {
  button.addEventListener("click", async () => {
    try {
      const response = await fetch(`${API_BASE}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ SelectedAnswer: button.innerText })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log("Question: ", data.question);
      console.log("Options: ", data.options);
      console.log("Found: ", data.found);

      questionCount++;
      question_number.innerText = questionCount;

      if (data.found === 1) {
        window.location.href = `/answers.html?name=${encodeURIComponent(data.options[0])}`;
        return;
      }

      if (data.found === -1) {
        alert("Sorry, couldn't find your character!");
        await initializeGame();
        return;
      }

      answer_box.innerHTML = '';
      data.options.forEach(option => {
        generateNewOptions(option);
      });
      generateNewQuestion(data.question);

    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred. Please try again.");
    }
  });
}

async function initializeGame() {
  try {
    const response = await fetch(`${API_BASE}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Initial Question: ", data.question);
    console.log("Initial Options: ", data.options);

    questionCount = 1;
    question_number.innerText = questionCount;
    
    answer_box.innerHTML = '';
    data.options.forEach(option => {
      generateNewOptions(option);
    });
    generateNewQuestion(data.question);

  } catch (error) {
    console.error("Error initializing game:", error);
    question_box.innerHTML = "Error loading game. Please refresh the page.";
  }
}

initializeGame();