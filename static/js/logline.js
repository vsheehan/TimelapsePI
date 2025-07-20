class LiveLogAppender {
    constructor(socket, tableId = "capture-log") {
      this.socket = socket;
      this.table = document.getElementById(tableId);
  
      if (!this.socket || !this.table) {
        console.warn("[LiveLogAppender] Missing socket or table element.");
        return;
      }
  
      this.listen();
    }
  
    listen() {
      this.socket.on("log_line", (entry) => {
        this.append(entry);
      });
    }
  
    append(entry) {
      const row = document.createElement("tr");
      row.classList.add("log-line", `log-level-${entry.level.toLowerCase()}`);
  
      row.innerHTML = `
        <td class="log-date">${entry.timestamp}</td>
        <td class="log-level">${entry.level}</td>
        <td class="log-category">${entry.category}</td>
        <td class="log-message">
          <span class="log-file">${entry.file || "?"}:${entry.line ?? "?"}</span>
          ${entry.message}
        </td>
      `;
  
      this.table.appendChild(row);
      this.table.parentElement.scrollTop = this.table.parentElement.scrollHeight;
    }
  }


  document.addEventListener("DOMContentLoaded", () => {
    if (window.socket) {
      new LiveLogAppender(window.socket);
    } else {
      console.warn("SocketIO not found on window.socket");
    }
  });