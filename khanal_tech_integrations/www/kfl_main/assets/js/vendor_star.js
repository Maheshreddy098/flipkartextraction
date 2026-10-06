document.addEventListener("DOMContentLoaded", function () {
    const button = document.getElementById("fetchVendorButton");
  
    if (button) {
      button.addEventListener("click", () => {
        // Optional: stop blinking after click
        button.classList.remove("blinking-star");
  
        // Confetti burst effect
        confetti({
            particleCount: 40,
            spread: 120,
            origin: { y: 0.6 },
            shapes: ["star"],
            scalar: 1.3,
            colors: ["#FFA500", "#FFB300", "#FFD700", "#FFC107"], // Orange & Dark Yellow tones
          });
          
  
        // Optional: re-enable blinking after short delay
        setTimeout(() => {
          button.classList.add("blinking-star");
        }, 1500);
  
        console.log("Fetching Vendor Supply Data...");
      });
    }
  });
  