

document.addEventListener("DOMContentLoaded", function() {
    // Make the button go blue when it's selected
    let inputs_answer = document.querySelectorAll(".answer-grid input");
    let last_selected;

    for(let i = 0; i < inputs_answer.length; i++){
        inputs_answer[i].addEventListener("change", function(){

            inputs_answer[i].closest(".answer-grid").style.backgroundColor = "blue";
            
        });
    }
});
