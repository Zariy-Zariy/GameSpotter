document.addEventListener("DOMContentLoaded", function() {
    let questions = document.querySelectorAll(".question");

    for (let i = 0; i < questions.length; i++){

        let inputs_answer = questions[i].querySelectorAll(".answer input");
        let last_selected;
    
        for(let j = 0; j < inputs_answer.length; j++){
            inputs_answer[j].addEventListener("click", function(){
                // Make the button go blue when it's selected
                if(last_selected != undefined){
                    last_selected.parentElement.style.backgroundColor = "#474554";
                }                                                   
    
                inputs_answer[j].parentElement.style.backgroundColor = "#3c28bd";
                last_selected = inputs_answer[j];

                // Make the page scroll automatically into the next question
                if (i + 1 < questions.length){
                    questions[i + 1].scrollIntoView();
                }
    
            });
        }
    }

});
