function previewFingerprint(event){
    let preview = document.getElementById("fingerprintPreview");
    let scanner = document.getElementById("scannerLine");

    preview.src = URL.createObjectURL(event.target.files[0]);
    preview.style.display = "block";
    scanner.style.display = "block";
}

function showLoading(){
    document.getElementById("loader").style.display="block";
    let progress = 0;
    let bar = document.getElementById("progressBar");
    let text = document.getElementById("loadingText");
    let messages = [
        "Analyzing fingerprint...",
        "Processing ridge patterns...",
        "Extracting fingerprint features...",
        "Predicting blood group using AI..."
    ];
    let interval = setInterval(()=>{
        progress += 10;
        bar.style.width = progress + "%";
        if(progress == 30){ text.innerText = messages[1]; }
        if(progress == 60){ text.innerText = messages[2]; }
        if(progress == 80){ text.innerText = messages[3]; }
        if(progress >= 100){ clearInterval(interval); }
    },400);
}