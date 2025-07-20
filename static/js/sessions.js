class SessionsUI {
    constructor() {
      this.modal = new Modal();
      this.wrapper = document.getElementById("sessions-list");
      this.noSessions = document.getElementById("no-sessions");
      this.selected = new Set();
      this.zipLock = false;
  
      this.loadSessions();
      this.bindSocketListeners();
      this.bindCheckboxWatcher();
    }
  
    async loadSessions() {
      const res = await fetch("/session/");
      const sessions = await res.json();
  
      this.wrapper.innerHTML = "";
      if (!sessions.length) {
        this.noSessions.style.display = "block";
        return;
      }
  
      this.noSessions.style.display = "none";
  
      // Sort descending by started_at
      sessions.sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
      sessions.reverse().forEach(session => {
        this.addSession(session)});
    }
  
    addSession(session) {
      const id = session.session_id;
      const el = document.createElement("div");
      el.classList.add("session-row");
      el.dataset.sessionId = id;
      el.innerHTML = this.renderSession(session, true);
  
      // Preserve checkbox state
      
      const isChecked = this.selected.has(id);
      this.wrapper.insertBefore(el, this.wrapper.firstChild);
      
      if (isChecked) {
        const checkbox = el.querySelector(".session-select");
        if (checkbox) checkbox.checked = true;
      }
  
      this.bindRowActions(el);
    }
  

    renderSession(session, listView = true) {
      if (!session || !session.session_id) return "<div>No session available.</div>";
      const hasEnded = !!session.ended_at;
      const endedDisplay = hasEnded ? formatDateTime(session.ended_at) : "N/A";
      const statusText = hasEnded ? "Complete" : "In Progress...";
      const statusClass = hasEnded ? "inactive" : "active";
      const label = listView ? "" : `<legend>${hasEnded ? "Latest Session" : "Current Session"}</legend>`;
      const rowspan = 6; // Always 4 rows above the status row
    
      // --- Optional ZIP logic ---
      //const hasZip = !!session.zip_file;

      const hasZip = !!session.zip_file ? session.zip_size : false;
    
      const checkboxCol = listView && false
        ? `<td class="session-checkbox" rowspan="${rowspan}">
            <input type="checkbox" class="session-select" data-session-id="${session.session_id}" />
          </td>`
        : "";

      
    
      const actionCol = listView ? 
      `<td class="session-button-wrapper" rowspan="${rowspan}">
        <div class="button-group" data-session-id="${session.session_id}">
          ${this.getButtons(session.session_id, hasZip, hasEnded)}
        </div>
      </td>` : 
      "";
    
      return `
        ${label}
        <table class="session-table ${hasEnded ? "session-complete" : "session-active"}">
          <tr>
            ${checkboxCol}
            <td class="session-thumbnail" rowspan="${rowspan-1}" data-field="thumbnail">
              <img src="/session/${session.session_id}/thumbnail" />
            </td>
            <td class="session-header">ID:</td>
            <td class="session-data" data-field="session-id">${session.session_id}</td>
            ${actionCol}
          </tr>
          <tr>
            <td class="session-header">Interval:</td>
            <td class="session-data" data-field="interval">${session.interval} Seconds</td>
          </tr>
          <tr>
            <td class="session-header">Started:</td>
            <td class="session-data" data-field="started">${formatDateTime(session.started_at)}</td>
          </tr>
          <tr>
            <td class="session-header">Ended:</td>
            <td class="session-data" data-field="ended">${endedDisplay}</td>
          </tr>
          <tr>
            <td class="session-header">Uptime:</td>
            <td class="session-data ${ hasEnded ? '' : 'live-uptime' }" ${ hasEnded ? '' : 'data-started="'+session.started_at+'"'}  data-field="uptime">${session.uptime || "—"}</td>
          </tr>
          <tr>
            <td class="session-status ${statusClass}">${statusText}</td>
            <td class="session-header">Captures:</td>
            <td class="session-data" data-field="file-count">${session.file_count}</td>
          </tr>
        </table>
      `;
    }

    getButtons(sessionId, hasZip, hasEnded, isZipping = false) {
      if (isZipping) {
        return `
          <button class="zip-cancel" data-session-id="${sessionId}">Cancel ZIP</button>
          <button class="session-delete" data-session-id="${sessionId}" disabled>Delete Session</button>
        `;
      }
      
      return `
        ${hasZip ? `
          <div class="zip-size">${this.formatBytes(hasZip)}</div>
          <button class="zip-download" data-session-id="${sessionId}" ${hasEnded ? '' : 'disabled'}>Download ZIP</button>
          <button class="zip-delete" data-session-id="${sessionId}" ${hasEnded ? '' : 'disabled'}>Delete ZIP</button>`
        : `
          <button class="zip-create" data-session-id="${sessionId}" ${hasEnded ? '' : 'disabled'}>Create ZIP</button>`}
        <button class="session-delete" data-session-id="${sessionId}" ${hasEnded ? '' : 'disabled'}>Delete Session</button>
      `;
    }

    removeSession(sessionId) {
      const el = this.getSessionElement(sessionId);
      if (el) el.remove();
      this.selected.delete(sessionId);
      if (!this.wrapper.children.length) {
        this.noSessions.style.display = "block";
      }
    }
  
    updateSession(session, latestSession = false, isZipping = false) {
      const el = latestSession
        ? document.getElementById("latest-session-wrapper")
        : this.getSessionElement(session.session_id);

      if (!el && !latestSession ) {
        this.addSession(session);
        return;
      }

      if (latestSession) {
        const idField = el.querySelector('[data-field="session-id"]');
        if (!idField || idField.textContent !== session.session_id) {
          el.innerHTML = this.renderSession(session, false);
          return;
        }
      }


      // --- 1. Only update thumbnail if file count ≤ 2 ---
      if (session.file_count <= 2) {
        const thumb = el.querySelector("img");
        if (thumb) {
          thumb.src = `/session/${session.session_id}/thumbnail?${Date.now()}`;
        }
      }

      // --- 2. Update file count if changed ---
      const fileCountCell = el.querySelector('[data-field="file-count"]');
      if (fileCountCell && fileCountCell.textContent !== String(session.file_count)) {
        fileCountCell.textContent = session.file_count;
      }

      // --- 3. If session ended, update ended, status, uptime ---
      if (session.ended_at) {
        const endedCell = el.querySelector('[data-field="ended"]');

        //const endedCell = el.querySelector("td:has(.session-header:contains('Ended')) + .session-data");
        if (endedCell) endedCell.textContent = formatDateTime(session.ended_at);

        const statusCell = el.querySelector(".session-status");
        if (statusCell) {
          statusCell.textContent = "Complete";
          statusCell.classList.remove("active");
          statusCell.classList.add("inactive");
        }

        const uptimeCell = el.querySelector(".live-uptime");
        if (uptimeCell) {
          uptimeCell.classList.remove("live-uptime");
          uptimeCell.removeAttribute("data-started");
          uptimeCell.textContent = session.uptime;
        }

        el.classList.remove("session-active");
        el.classList.add("session-complete");
      }

      // --- 4. If still live, ensure data-started is set for live ticking ---
      const uptimeCell = el.querySelector(".live-uptime");
      if (!session.ended_at && uptimeCell && uptimeCell.dataset.started !== session.started_at) {
        uptimeCell.dataset.started = session.started_at;
      }


      const hasZip = !!session.zip_file ? session.zip_size : false;
      // --- 5. Update ZIP buttons ---
      const btnGroup = el.querySelector(".button-group");
      if (btnGroup) {
        btnGroup.innerHTML = this.getButtons(session.session_id, hasZip, !!session.ended_at, isZipping);
        this.bindButtonActions(el);
      }

      // --- 6. Cache file count if available ---
      el.dataset.fileCount = session.file_count;
    }





  
    getSessionElement(sessionId) {
      return this.wrapper.querySelector(`.session-row[data-session-id="${sessionId}"]`);
    }
  
    bindRowActions(row) {
      this.bindButtonActions(row);
      this.bindCheckbox(row);
    }
  
    bindCheckbox(row) {
      const checkbox = row.querySelector(".session-select");
      if (checkbox) {
        checkbox.addEventListener("change", () => {
          this.updateMultiselectUI();
        });
      }
    }

    bindButtonActions(row) {
      const sessionId = row.dataset.sessionId;

      // --- Create ZIP ---
      const zipBtn = row.querySelector(".zip-create");
      if (zipBtn) {
        zipBtn.addEventListener("click", () => {
          if (this.zipLock) return;

          this.zipLock = true;
          zipBtn.disabled = true;
          zipBtn.textContent = "Zipping...";

          fetch(`/session/${sessionId}/zip`, { method: "POST" })
            .catch(err => console.error("ZIP create failed", err));
        });
      }

      // --- Download ZIP ---
      const zipDownload = row.querySelector(".zip-download");
      if (zipDownload) {
        zipDownload.addEventListener("click", () => {
          window.open(`/session/${sessionId}/zip/download`, "_blank");
        });
      }

      // --- Delete ZIP ---
      const zipDelete = row.querySelector(".zip-delete");
      if (zipDelete) {
        zipDelete.addEventListener("click", () => {
          fetch(`/session/${sessionId}/zip/delete`, { method: "POST" })
            .then(() => this.reloadSession(sessionId))
            .catch(err => console.error("ZIP delete failed", err));
        });
      }

      // --- Delete Session ---
      const delBtn = row.querySelector(".session-delete");
      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          const confirmed = await this.modal.confirm(
            `<span style="color:red;font-weight:bold;">WARNING:</span> This will delete all captures and zip files associated with this session. This cannot be undone. Are you sure?`
          );
          if (confirmed) {
            fetch(`/session/${sessionId}`, { method: "DELETE" });
          }
        });
      }

      const cancelBtn = row.querySelector(".zip-cancel");
        if (cancelBtn) {
          cancelBtn.addEventListener("click", () => {
            fetch(`/session/zip/cancel`, { method: "POST" });
          });
        }
    }

    reloadSession(sessionId) {
      fetch(`/session/${sessionId}`)
        .then(res => res.json())
        .then(data => this.updateSession(data));
    }
  
    bindSocketListeners() {
      if (!window.socket) return;
      socket.on('remove-session', data => console.log('REMOVE SESSION:', data));
      socket.on("add-session", session => this.addSession(session));
      socket.on("remove-session", ({ session_id }) => this.removeSession(session_id));
      socket.on("update-session", session => this.updateSession(session));
  
      socket.on("zip-started", ({ session_id }) => {
        this.zipLock = true;
        this.zipSession = session_id;
        this.updateSessionUIButtons();  // disables all zip buttons
        this.addProgressBar(session_id);
        this.updateSession({ session_id }, false, true); // re-renders button group as cancel button
      });
  
      socket.on("zip-progress", ({ session_id, percent }) => {
        this.updateProgress(session_id, percent);
        
      });

      socket.on("zip-complete", ({ result }) => {
        let session_id = result.session_id;
        this.zipLock = false;
        this.removeProgressBar(session_id);
        this.updateSessionUIButtons(); // re-enable zip buttons
        this.reloadSession(session_id);
        window.open(`/session/${session_id}/zip/download`, "_blank");
        this.zipSession = false
      });
  
      socket.on("zip-error", ({ session_id }) => {
        this.zipLock = false;
        this.removeProgressBar(session_id);
        this.updateSessionUIButtons(); // re-enable zip buttons
        if (this.zipSession) {
          this.reloadSession(this.zipSession);
        }
        this.zipSession = false
      });

      socket.on("zip-cancelled", ({ session_id }) => {
        this.zipLock = false;
        this.removeProgressBar(session_id);
        this.updateSessionUIButtons(); // re-enable zip buttons
        if (this.zipSession) {
          this.reloadSession(this.zipSession);
        }
        this.zipSession = false
      });
    }
  
    bindCheckboxWatcher() {
      // Optional: bind multiselect toolbar toggles here
    }
  
    updateMultiselectUI() {
      // Optional: show/hide multiselect action bar
    }

    addProgressBar(sessionId) {
      const el = this.getSessionElement(sessionId);
      if (!el) return;

      let existing = el.querySelector(".zip-progress");
      if (existing) return;

      const bar = document.createElement("div");
      bar.className = "zip-progress";
      bar.innerHTML = `
        <div class="progress-bar">
          <div class="progress-fill" style="width: 0%"></div>
        </div>
      `;

      el.appendChild(bar);
    }

    updateProgress(sessionId, percent) {
      const el = this.getSessionElement(sessionId);
      if (!el) return;

      const fill = el.querySelector(".progress-fill");
      if (fill) fill.style.width = `${percent}%`;
    }

    removeProgressBar(sessionId) {
      const el = document.querySelectorAll('.zip-progress');
      el.forEach((prog)=> {
        prog.remove();
      })
    }

    updateSessionUIButtons() {
      const buttons = document.querySelectorAll(".zip-create, .zip-delete, .zip-download, .session-delete");
      buttons.forEach(btn => btn.disabled = this.zipLock);
    }

    formatBytes(bytes, decimals = 1) {
      if (bytes === 0 || !bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      const size = parseFloat((bytes / Math.pow(k, i)).toFixed(decimals));
      return `${size} ${sizes[i]}`;
    }

}
  
  // --- Start the UI ---
  document.addEventListener("DOMContentLoaded", () => {
    window.SessionsUI = new SessionsUI();
  });
  