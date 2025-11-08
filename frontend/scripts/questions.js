// const question_box = document.querySelector(".question-text");

// let data = [];
// document.querySelectorAll(".answer-btn").forEach((button) => {
//   data.push(button.innerText);
// });

// function generateNewOptions(option) {
//   const newButton = document.createElement("button");
//   newButton.classList.add("answer-btn");
//   newButton.innerText = option;
//   document.querySelector(".answer-box").appendChild(newButton);
//   addingEvents(newButton);
// }

// function generateNewQuestion(question){
//     document.querySelector(".question-text").innerHTML = question;
// }

// function addingEvents(button) {
//   button.addEventListener("click", async () => {
//     const response = await fetch("http://127.0.0.1:8000/process", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ SelectedAnswer: button.innerText })
//     });

//     document.querySelector(".question-number").innerText = Number(document.querySelector(".question-number").innerText) + 1;

//     data = await response.json();
//     console.log("Question: ", data.question);
//     console.log("Options: ", data.options);
//     console.log("Found: ", data.found);
//     if (data.found === 1) {
//     window.location.href = `/answers.html?name=${encodeURIComponent(data.options[0])}`;
//     }
//     document.querySelector(".answer-box").innerHTML = '';
//     data.options.forEach(option => {
//       generateNewOptions(option); 
//     })
//     generateNewQuestion(data.question); 
//     if(data.found == -1){
//       console.log("Load defeat page!");
//     }
//     else if(data.found){
//       console.log("Load anwers page!");
//     }
//   });
// }

// document.querySelectorAll(".answer-btn").forEach(button => {
//   addingEvents(button);
// })
const question_box = document.querySelector(".question-text");
const answer_box = document.querySelector(".answer-box");
const question_number = document.querySelector(".question-number");

let questionCount = 0;

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
      const response = await fetch("http://127.0.0.1:8000/process", {
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

      // Check if found
      if (data.found === 1) {
        window.location.href = `/answers.html?name=${encodeURIComponent(data.options[0])}`;
        return;
      }

      // Check if not found
      if (data.found === -1) {
        alert("Sorry, couldn't find your character!");
        // Reset the game
        await initializeGame();
        return;
      }

      // Update question and options
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

// Initialize the game by resetting state and getting first question
async function initializeGame() {
  try {
    const response = await fetch("http://127.0.0.1:8000/reset", {
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
    
    // Clear and populate options
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

// Initialize game on page load
initializeGame();