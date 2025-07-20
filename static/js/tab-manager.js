// static/js/tab-manager.js

class TabManager {
    constructor(navSelector = '.nav-tab', tabSelector = '.tab') {
      this.navTabs = document.querySelectorAll(navSelector);
      this.tabs = document.querySelectorAll(tabSelector);
      this.bindEvents();
    }
  
    bindEvents() {
      this.navTabs.forEach(navTab => {
        navTab.addEventListener('click', () => {
          const tabID = navTab.dataset.id;
          const tab = document.getElementById(tabID);
          if (!tab || navTab.classList.contains('disabled')) return;
  
          this.clearSelection();
          navTab.classList.add('selected');
          tab.classList.add('selected');
  
          if (tabID === "log") {
            const logContainer = document.getElementById("capture-log");
            if (logContainer) {
              logContainer.scrollTop = logContainer.scrollHeight;
            }
          }
        });
      });
    }
  
    clearSelection() {
      this.navTabs.forEach(tab => tab.classList.remove('selected'));
      this.tabs.forEach(tab => tab.classList.remove('selected'));
    }
  
    static init() {
      return new TabManager();
    }
  }
  
  
  document.addEventListener("DOMContentLoaded", () => TabManager.init());
  