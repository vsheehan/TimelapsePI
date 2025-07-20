// static/js/modal.js

class Modal {
    constructor() {
      this.backdrop = document.getElementById("modal-backdrop");
      this.messageBox = document.getElementById("modal-message");
      this.confirmBtn = document.getElementById("modal-confirm");
      this.cancelBtn = document.getElementById("modal-cancel");
      this.resolve = null;
  
      this.confirmBtn.addEventListener("click", () => this._resolve(true));
      this.cancelBtn.addEventListener("click", () => this._resolve(false));
    }
  
    _resolve(result) {
      this.backdrop.classList.add("hidden");
      if (this.resolve) this.resolve(result);
      this.resolve = null;
    }
  
    async confirm(message = "Are you sure?") {
      this.messageBox.innerHTML = message;
      this.backdrop.classList.remove("hidden");
      return new Promise(resolve => {
        this.resolve = resolve;
      });
    }
  }
  