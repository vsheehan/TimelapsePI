class CameraUI {
    constructor() {
      this.latestImg = document.getElementById("latest");
      this.streamImg = document.getElementById("stream-img");
  
      this.camLatest = document.getElementById("cam-latest");
      this.camLive   = document.getElementById("cam-live");
      this.warning   = document.getElementById("cam-live-warning");
  
      this.startBtn = document.getElementById("start-timelapse");
      this.stopBtn  = document.getElementById("stop-timelapse");
      this.liveBtn  = document.getElementById("toggle-live-view");
  
      this.settingsTab = document.getElementById('settings-tab-button');

      this.debouncedUpdateUI = debounce(this.updateUI.bind(this), 150);

      this.bindEvents();
      this.initSocketListeners();
  
      // Fallback for no sockets
      this.pollInterval = setInterval(() => this.fetchStatus(), 10000);
      this.fetchStatus();
    }
  
    bindEvents() {
        this.startBtn.addEventListener("click", () => {
            if (this.startBtn.classList.contains("disabled")) return;
            this.startBtn.classList.add("disabled")
            this.startCapture();
        });

        this.stopBtn.addEventListener("click", () => {
            if (this.stopBtn.classList.contains("disabled")) return;
            this.stopBtn.classList.add("disabled")
            this.setOverlayVisible(true);
            fetch("/camera/capture/stop", { method: "POST" })
              .catch(console.error);
            this.settingsTab.classList.remove('disabled');
        });
  
        this.liveBtn.addEventListener("click", () => {
            if (this.liveBtn.classList.contains("disabled")) return;
            this.liveBtn.classList.add("disabled")
            const isRunning = this.liveBtn.classList.contains("running");
            const url = isRunning ? "/camera/stream/stop" : "/camera/stream/start";
          
            this.setOverlayVisible(true);
            fetch(url, { method: "POST" })
              .catch(console.error);
        });
    }
  
    initSocketListeners() {
      if (!window.socket) return;
  
      socket.on("status-update", (data) => this.debouncedUpdateUI(data));
      socket.on("image-updated", () => this.refreshLatestImage());
    }
  
    async fetchStatus() {
      const res = await fetch("/system/status");
      const data = await res.json();
      this.debouncedUpdateUI(data);
    }
  

    startCapture() {
      this.setOverlayVisible(true);
      const form = document.getElementById('cam-controls-form');
      const formData = new FormData(form);

      fetch("/settings", {
          method: "POST",
          body: formData
        })
        .then(res => {
          if (!res.ok) throw new Error("Failed to save");
          return res.text();
        })
        .then(() => {
          showInfo("Settings saved successfully", "success");
          fetch("/camera/capture/start", { method: "POST" })
            .catch(console.error);
          this.settingsTab.classList.add('disabled');
        })
        .catch(err => {
          this.saveBtn.classList.add("red");
          showInfo("Failed to save settings", "error", false);
          setTimeout(() => this.saveBtn.classList.remove("red"), 2500);
        });

      
      
      

       
        
    }

    updateUI(data) {

      const mode = data.mode;
      const session = data.latest_session;
      const system = data.system;
      
      window.latestSessionId = session.session_id;
      // Toggle live/preview
      this.camLatest.classList.toggle("hidden", mode === "streaming");
      this.camLive.classList.toggle("hidden", mode !== "streaming");
      this.warning.style.display = mode === "capture" ? "block" : "none";
  
      // Button states
      this.startBtn.classList.toggle("disabled", mode !== "idle");
      this.stopBtn.classList.toggle("disabled", mode !== "capture");
      this.liveBtn.classList.toggle("disabled", mode === "capture");
      this.liveBtn.classList.toggle("running", mode === "streaming");
      this.liveBtn.textContent = mode === "streaming" ? "Stop Live View" : "Live View";
      
      this.settingsTab.classList.toggle("disabled", mode === "capture");
      console.log(data)
      // Live stream
      if (mode === "streaming") {
        const hostname = window.location.hostname;
        const protocol = window.location.protocol;
        let url = `${protocol}//${hostname}:8080/`
        if (!data.libcamera) { url += "?action=stream" }
        
        this.streamImg.src = url;
      } else {
        this.streamImg.src = "";
      }
      //console.log(mode);
      if (mode !== "capture") {
        this.latestImg.src = "static/placeholder.jpg"
      } else {
        this.refreshLatestImage()
      }
      
      if (window.SessionsUI && typeof window.SessionsUI.updateSession === "function") {
        if (session.status != 'idle') {
          window.SessionsUI.updateSession(session);
        }
        window.SessionsUI.updateSession(session, true);
      }

      //document.getElementById("latest-session-wrapper").innerHTML = renderSession(session, false);

      
      this.renderSystemStatus(system);
      this.setOverlayVisible(false);
    }
  
    refreshLatestImage() {
      const now = new Date().getTime();
      this.latestImg.src = `/camera/latest.jpg?t=${now}`;
    }

    setOverlayVisible(visible) {
        const overlay = document.getElementById("cam-overlay");
        overlay.classList.toggle("hidden", !visible);
    }


    renderSystemStatus(system) {
      const wrapper = document.getElementById("system-wrapper");
      if (!system || !system.disk) {
        wrapper.innerHTML = "<div>System status unavailable.</div>";
        return;
      }
    
      wrapper.innerHTML = `
        <div><strong>Temp:</strong> ${system.temperature_celsius || "N/A"}</div>
        <div><strong>CPU:</strong> ${system.cpu_load || "N/A"}</div>
        <div><strong>Memory:</strong> ${system.memory_usage || "N/A"}%</div>
        <div><strong>Disk:</strong> ${formatStorageSize(system.disk.used_mb)} / ${formatStorageSize(system.disk.total_mb)} (${system.disk.percent_used}%)</div>
      `;
    }
  


  }
  
  

  
  // --- Start the UI ---
  document.addEventListener("DOMContentLoaded", () => {
    window.CameraUI = new CameraUI();
  });
  