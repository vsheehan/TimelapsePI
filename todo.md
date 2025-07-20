# 🛠️ TimelapsePI Production Plan

A structured checklist of improvements and features to finalize the TimelapsePI system for production and public release.


# 📝 TimelapsePi TODO List

## 🧰 Hardware Support

- [ ] Add RGB LED indicator for capture state:
  - Green = Capturing
  - Red = Idle
- [ ] Add 2 indicator LEDs:
  - Wi-Fi mode
  - Hotspot mode
- [ ] Add hardware button to:
  - [ ] Toggle between Wi-Fi and Hotspot modes
  - [ ] Start/Stop capture
- [ ] 3D Printed Case
- [ ] Pi Camera w/ Optional USB Cam Overide 

---

## ⚙️ Deployment & Setup

- [ ] Add `setup.sh` script to:
  - Create virtualenv
  - Install dependencies from `requirements.txt`
  - Set up file structure
  - Optionally sanitize and push to GitHub
- [ ] Add `requirements.txt`
- [ ] Add `README.md` with:
  - Description and usage
  - Setup instructions
  - Screenshots or demo
- [ ] Provide example config files for:
  - Hotspot mode (`hostapd`, `dnsmasq`)
  - DHCP/static setup (`dhcpcd.conf`)


## 🗂️ File Structure Targets

```
~/timelapse/
├── data/
│   └── config/
│       └── config.json
│       └── sessions.json
│   └── downloads/
│       └── *.zip
│   └── logs/*.logs
│   └── sessions/
│       └── YYYYMMDD-HHii/*.jpg
│   └── latest.jpg
├── lib/
├── routes/
├── static/
├── templates/
├── venv/
└── boot.py
└── app.py
```


> ✅ Mark off each item as it is completed in your GitHub issues or with project milestones.