// static/js/settings-ui.js

class SettingsUI {
    constructor(modalInstance) {
      this.modal = modalInstance;
      this.saveBtn = document.getElementById("save-button");
      this.rebootBtn = document.getElementById("rebootBtn");
      this.shutdownBtn = document.getElementById("shutdownBtn");
      this.resolutionSelect = document.getElementById("resolution");
      this.filteredResolutionSelect = document.querySelectorAll(".filtered-resolutions");
      this.toggleFields = document.querySelectorAll(".field-toggle");
      this.advancedToggle = document.getElementById("advanced-toggle");
      this.advancedToggleWrapper = document.getElementById("advanced-toggle-wrapper");
      this.advancedFields = document.querySelectorAll(".advanced-setting");
      this.linkedFields = [
        document.getElementById('home-interval'),
        document.getElementById('interval'),
        document.getElementById('home-change-detect'),
        document.getElementById('change-detect')
      ]
      this.cameraModeField = document.getElementById('camera-type');

      this.bindEvents();
    }
  
    bindEvents() {
      this.saveBtn?.addEventListener("click", () => this.saveSettings());
      this.resolutionSelect?.addEventListener("change", () => this.updateAspectRatios());
      this.advancedToggleWrapper?.addEventListener("click", (e) => this.toggleAdvanced(e));
      this.cameraModeField?.addEventListener('change', () => this.cameraModeToggle());

      this.linkedFields.forEach((field) => {
        field.addEventListener('change', (e) => this.linkedFieldChanged(e));
      });

      this.toggleFields.forEach(toggle => {
        toggle.addEventListener("change", () => this.toggleField(toggle));
      });
  
      this.rebootBtn?.addEventListener("click", async () => {
        const confirmed = await this.modal.confirm("Are you sure you want to reboot?");
        if (confirmed) this.reboot();
      });
  
      this.shutdownBtn?.addEventListener("click", async () => {
        const confirmed = await this.modal.confirm("Are you sure you want to shut down?");
        if (confirmed) this.shutdown();
      });
    }
  
    linkedFieldChanged(event) {
      let source = event.target;
      
      let tempId = source.id,
          id     = tempId.startsWith("home-") ? tempId.replace(/^home-/, "") : "home-" + tempId,
          target = document.getElementById(id);

      if (target) target.value = source.value;
    }

    cameraModeToggle() {
      console.log(this.cameraModeField);
      const afWrapper        = document.getElementById('autofocus-mode-wrapper'),
            deviceWrapper    = document.getElementById('video-device-wrapper'),
            isUsb            = this.cameraModeField.value === 'usb';
      afWrapper.classList.toggle('camera-hidden', isUsb);
      deviceWrapper.classList.toggle('camera-hidden', !isUsb);

    }

    toggleField(toggle) {
      const field = document.getElementById(toggle.dataset.toggleId);
      const visible = toggle.value !== 'true';
      field?.classList.toggle("hidden", visible);
    }
  
    toggleAdvanced(event) {
      if (event.target !== this.advancedToggle) {
        this.advancedToggle.checked = !this.advancedToggle.checked;
      }
      this.advancedFields.forEach(field => {
        field.classList.toggle("hidden", !this.advancedToggle.checked);
      });
      this.advancedToggleWrapper.setAttribute("aria-expanded", this.advancedToggle.checked);
    }
  
    updateAspectRatios() {
      const selected = this.resolutionSelect.selectedOptions[0];
      if (!selected) return console.warn("No resolution selected");
  
      const aspectRatio = selected.dataset.aspectRatio;
      const thumbRes = window.appConfig.thumbnail_resolution;
      const previewRes = window.appConfig.preview_resolution;
  
      fetch(`/camera/resolutions?aspect_ratio=${encodeURIComponent(aspectRatio)}`)
        .then(res => res.json())
        .then(data => {
          this.filteredResolutionSelect.forEach(select => {
            const targetRes = select.id === "preview-resolution" ? previewRes : thumbRes;
            select.innerHTML = "";
  
            data.forEach(res => {
              const option = new Option(`${res.resolution} (${res.aspect_ratio})`, res.resolution);
              option.dataset.aspectRatio = res.aspect_ratio;
              option.selected = res.resolution === targetRes;
              select.appendChild(option);
            });
          });
        })
        .catch(err => {
          showInfo("Failed to fetch resolutions", "error", false);
          console.error(err);
        });
    }
  
    saveSettings() {
      const form = document.getElementById("settings-form");
      const formData = new FormData(form);
      this.saveBtn.classList.remove("red", "green");
  
      fetch("/settings", {
        method: "POST",
        body: formData
      })
      .then(res => {
        if (!res.ok) throw new Error("Failed to save");
        return res.text();
      })
      .then(() => {
        this.saveBtn.classList.add("green");
        showInfo("Settings saved successfully", "success");
        setTimeout(() => this.saveBtn.classList.remove("green"), 2500);
      })
      .catch(err => {
        this.saveBtn.classList.add("red");
        showInfo("Failed to save settings", "error", false);
        setTimeout(() => this.saveBtn.classList.remove("red"), 2500);
      });
    }
  
    reboot() {
      fetch("/system/reboot", { method: "POST" })
        .then(res => res.json())
        .then(data => {
          if (data.status === "rebooting") {
            showInfo("Rebooting... system will go offline shortly.", "info", false);
          } else {
            showInfo("Reboot failed: " + (data.message || "Unknown error"), "error", false);
          }
        })
        .catch(() => showInfo("Request failed.", "error", false));
    }
  
    shutdown() {
      fetch("/system/shutdown", { method: "POST" })
        .then(res => res.json())
        .then(data => {
          if (data.status === "shutting down") {
            showInfo("Shutting down... system will go offline shortly.", "info", false);
          } else {
            showInfo("Shutdown failed: " + (data.message || "Unknown error"), "error", false);
          }
        })
        .catch(() => showInfo("Request failed.", "error", false));
    }
  
    static init(modalInstance) {
      const ui = new SettingsUI(modalInstance);
      ui.updateAspectRatios();
      ui.toggleAdvanced({ target: ui.advancedToggle });
    }
  }
  

  document.addEventListener("DOMContentLoaded", () => {
    const modal = new Modal();
    SettingsUI.init(modal);
  });
  