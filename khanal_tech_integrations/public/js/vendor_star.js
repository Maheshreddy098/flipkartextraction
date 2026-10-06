window.triggerConfetti = function () { 
  if (typeof confetti !== 'function') {
    console.error('Confetti library not loaded!');
    return;
  }
  confetti({
    particleCount: 40,
    spread: 120,
    origin: { x : 0.5, y: 0.5 },
    shapes: ["star"],
    scalar: 1.3,
    colors: ["#FFA500", "#FFB300", "#FFD700", "#FFC107"]
  });
};