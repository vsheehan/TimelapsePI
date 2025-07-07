
//Tab Navigation
const navTabs = document.querySelectorAll('.nav-tab');
const tabs    = document.querySelectorAll('.tab');

navTabs.forEach(function(navTab) {
  navTab.addEventListener('click', function() {
    const tabID = this.dataset.id;
    const tab   = document.getElementById(tabID);

    // Remove 'selected' from all nav tabs
    navTabs.forEach(tab => tab.classList.remove('selected'));

    // Remove 'selected' from all tab contents
    tabs.forEach(tab => tab.classList.remove('selected'));

    // Add 'selected' to the clicked nav tab and its corresponding tab content
    this.classList.add('selected');
    tab.classList.add('selected');
    if (tabID === "log") {
      const logContainer = document.getElementById("capture-log");
      logContainer.scrollTop = logContainer.scrollHeight; // Auto scroll
    }
  });
});

// Settings Toggles
const autoStopToggle         = document.getElementById('auto-stop-enabled');
const autoStopWrapper        = document.getElementById('auto-stop-minutes-wrapper');
const changeDetectionToggle  = document.getElementById('change-detect');
const changeDetectionWrapper = document.getElementById('change-threshold-wrapper');
const saveBtn                = document.getElementById('save-button');


autoStopToggle.addEventListener('change', function() {
	const hide = this.value !== 'true'; 
	autoStopWrapper.classList.toggle('hidden', hide);
}); // ← you were missing this

changeDetectionToggle.addEventListener('change', function() {
	const hide = this.value !== 'true';
	changeDetectionWrapper.classList.toggle('hidden', hide);
});

saveBtn.addEventListener('click', function () {
  const form = document.getElementById('settings-form');
  const formData = new FormData(form);
  saveBtn.classList.remove('red');
  saveBtn.classList.remove('green');
  fetch('/settings', {
    method: 'POST',
    body: formData
  })
  .then(res => {
    if (!res.ok) throw new Error('Failed to save');
    return res.text(); // or .json() depending on your backend
  })
  .then(data => {
    // Optional: show a confirmation message
    saveBtn.classList.add('green');
    setTimeout(() => { document.getElementById('save-button').classList.remove('green'); }, 2500);
  })
  .catch(err => {
    console.error(err);
    saveBtn.classList.add('red');
    setTimeout(() => { document.getElementById('save-button').classList.remove('red'); }, 2500);
  });
});

// Refresh the lastest image....
setInterval(() => {
  document.getElementById("latest").src = "/latest.jpg?" + new Date().getTime();
}, 5000);



// Download File management...


function updateZipList() {
  fetch("/zip-list")
    .then(res => res.json())
    .then(files => {
      const wrapper = document.getElementById("zip-list-wrapper");
      const list = document.getElementById("zip-list");
      list.innerHTML = "";

      wrapper.classList.toggle('hidden', files.length === 0);

      files.forEach(file => {
        const item = document.createElement("li");
        item.innerHTML = `
          <button class="delete-btn" data-filename="${file}">❌</button>  
          <a href="/downloads/${file}" download>${file}</a>
        `;
        list.appendChild(item);
      });
    });
}

let zipToDelete = null;

//Zip and Capture Deletion...
document.addEventListener("click", function (e) {
  if (e.target.classList.contains("delete-btn")) {
    zipToDelete = e.target.dataset.filename;
    document.getElementById("confirm-delete-modal").classList.remove("hidden");
  }

  if (e.target.id === "cancel-delete-btn") {
    zipToDelete = null;
    document.getElementById("confirm-delete-modal").classList.add("hidden");
    document.getElementById("delete-captures-checkbox").checked = false;
  }

  if (e.target.id === "confirm-delete-btn" && zipToDelete) {
    const deleteCaptures = document.getElementById("delete-captures-checkbox").checked;

    fetch("/delete-zip", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        filename: zipToDelete
      })
    }).then(res => res.json()).then(data => {
      if (data.status === "deleted" && deleteCaptures) {
        // Parse datetime range from zip filename
        const match = zipToDelete.match(/(\d{8}-\d{4})_(\d{8}-\d{4})/);
        if (match) {
          fetch("/delete-captures", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
              from_datetime: match[1].replace(/(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/, '$1-$2-$3T$4:$5'),
              to_datetime: match[2].replace(/(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/, '$1-$2-$3T$4:$5'),
            })
          });
        }
      }

      zipToDelete = null;
      document.getElementById("confirm-delete-modal").classList.add("hidden");
      document.getElementById("delete-captures-checkbox").checked = false;
    });
  }
});

//Sockets

const socket = io();

let progressVisible = false;

socket.on("zip_progress", (data) => {
  const wrapper = document.getElementById('download-progress-wrapper');
  const bar = document.getElementById("zip-progress-bar");
  const label = document.getElementById("zip-progress-label");
  
  if (!progressVisible) {
      wrapper.classList.remove("hidden");
      progressVisible = true;
  }

  bar.value = data.percent;
  label.innerText = `Zipping ${data.current} of ${data.total} files... (${data.percent}%)`;

  if (data.percent >= 100) {
    setTimeout(() => {
      wrapper.classList.add("hidden");
      bar.value = 0;
      label.textContent = "";
      progressVisible = false;
    }, 2500);  // Add slight delay to let user see 100%
  }

});

socket.on("zip_list_update", updateZipList);


function appendLogDiv(message, timestamp) {
  const logContainer = document.getElementById("capture-log");
  if (logContainer) {
    const line = document.createElement("div");
    const date = document.createElement("div");
    
    const msg  = document.createElement("div");
    line.classList.add('log-line');
    date.classList.add('log-date');
    msg.classList.add('log-msg');
    line.appendChild(date);
    line.appendChild(msg);
    date.textContent = `[${timestamp}]`;
    msg.textContent  = `${message}`;
    
    logContainer.appendChild(line);
    logContainer.scrollTop = logContainer.scrollHeight; // Auto scroll
  }
  
}


socket.on("log_line", (data) => {
  appendLogDiv(data.line, data.timestamp);
});

//Script start and stop

const camLatest = document.getElementById('cam-latest')
const camLive   = document.getElementById('cam-live');
const startBtn  = document.getElementById("start-timelapse");
const stopBtn   = document.getElementById("stop-timelapse");
const liveBtn   = document.getElementById("toggle-live-view");
const diskFree  = document.getElementById("free-space");
const diskPercent  = document.getElementById("free-percent");
const diskUsed  = document.getElementById("used-space");
const diskTotal  = document.getElementById("total-space");

function formatStorageSize(mb) {
    if (mb >= 1024 * 1024) {
        return (mb / (1024 * 1024)).toFixed(1) + ' TB';
    } else if (mb >= 1024) {
        return (mb / 1024).toFixed(1) + ' GB';
    } else {
        return mb.toFixed(1) + ' MB';
    }
}


function updateScriptStatus() {
  fetch("/status")
    .then(res => res.json())
    .then(data => {
      const status = data.status;
      camLatest.classList.toggle('hidden', status === 'streaming');
      camLive.classList.toggle('hidden', status !== 'streaming');
      updateStreamAddress(status === 'streaming');
      //statusIndicator.textContent = running ? "Running" : "Stopped";
      //statusIndicator.classList.toggle("running", running);
      //statusIndicator.classList.toggle("stopped", !running);
      startBtn.classList.toggle("disabled", status !== 'none' )
      stopBtn.classList.toggle("disabled", status !== 'capture')
      liveBtn.classList.toggle("disabled", status === 'capture')
      liveBtn.classList.toggle('running', status === 'streaming')
      if (status === "streaming") {
        liveBtn.textContent = "Stop Live View"
      } else {
        liveBtn.textContent = "Live View"
      }

      let disk = data.disk;

      console.log(data);
      diskFree.textContent = formatStorageSize(disk.free_mb);
      diskPercent.textContent = disk.percent_used;
      diskUsed.textContent = formatStorageSize(disk.used_mb);
      diskTotal.textContent = formatStorageSize(disk.total_mb);


    });
}



startBtn.addEventListener("click", () => {
  if (startBtn.classList.contains('disabled')) return;
  fetch("/start-capture", { method: "POST" })
    .then(() => updateScriptStatus());
});

stopBtn.addEventListener("click", () => {
  if (stopBtn.classList.contains('disabled')) return;
  fetch("/stop-capture", { method: "POST" })
    .then(() => updateScriptStatus());
});

liveBtn.addEventListener("click", () => {
  if (liveBtn.classList.contains('disabled')) return;
  if (liveBtn.classList.contains('running')) {
    fetch("/stop-streamer", { method: "POST" })
      .then(() => updateScriptStatus());
  } else {
    fetch("/start-streamer", { method: "POST" })
      .then(() => updateScriptStatus());  
  }

});

setInterval(() => {
  updateScriptStatus();
}, 10000); // every 10 seconds





// Initial population

function updateLogContent() {
  fetch("/log-content")
  .then(res => res.json())
  .then(lines => {
    const logContainer = document.getElementById("capture-log");
    logContainer.innerHTML = "";
    lines.forEach(({ timestamp, line }) => {
      appendLogDiv(line, timestamp);
    });
    logContainer.scrollTop = logContainer.scrollHeight;
  });
}

function updateStreamAddress(enable) {
  const streamImg = document.getElementById("stream-img");
  if (enable) {
    const hostname = window.location.hostname;
    const protocol = window.location.protocol;
    streamImg.src = `${protocol}//${hostname}:8080/?action=stream`;
  } else {
    streamImg.src = ''; 
  }
}

document.addEventListener("DOMContentLoaded", () => {
  updateZipList();
  updateScriptStatus();
  updateLogContent();
});

document.getElementById("reboot-button").addEventListener("click", () => {
  if (!confirm("Are you sure you want to reboot the system?")) return;

  fetch("/reboot", { method: "POST" })
    .then(res => res.json())
    .then(data => {
      const status = document.getElementById("reboot-status");
      if (data.status === "rebooting") {
        status.textContent = "Rebooting... system will go offline shortly.";
      } else {
        status.textContent = "Error: " + (data.message || "Unknown issue");
      }
    })
    .catch(err => {
      document.getElementById("reboot-status").textContent = "Request failed.";
    });
});