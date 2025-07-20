function showInfo(message, type = "info", autoHide = true) {
    const box = document.getElementById("info-box");
    if (!box) return;
  
    box.textContent = message;
    box.className = `info-box ${type}`;
    box.classList.remove("hidden");
  
    if (autoHide && type !== "error") {
      setTimeout(() => box.classList.add("hidden"), 4000);
    }
  }
  

  function startLiveUptimeCounter() {
    setInterval(() => {
      const now = Date.now();
      document.querySelectorAll(".live-uptime").forEach(el => {
        const started = el.dataset.started;
        if (!started) return;

        const startTime = new Date(started).getTime();
        const elapsed = Math.floor((now - startTime) / 1000); // in seconds

        const hrs = Math.floor(elapsed / 3600);
        const mins = Math.floor((elapsed % 3600) / 60);
        const secs = elapsed % 60;

        el.textContent = `${hrs}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
      });
    }, 1000);
  }
    


  function debounce(fn, delay) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => fn.apply(this, args), delay);
    };
  }


  
  // --- Utility Formatters ---
  function formatDateTime(isoStr) {
    if (!isoStr) return "—";
    const dt = new Date(isoStr);
    return dt.toLocaleString();
  }
  
  function formatStorageSize(mb) {
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  
    // --- Start the UI ---
  document.addEventListener("DOMContentLoaded", () => {
    startLiveUptimeCounter();
  });