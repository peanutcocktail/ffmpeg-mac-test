module.exports = {
  version: "7.0",
  title: "FFmpeg UV Test",
  description: "Minimal launcher to verify macOS uv-runtime FFmpeg dylib exposure.",
  menu: async (kernel, info) => {
    const installed = info.exists("app/env")
    const running = {
      install: info.running("install.js"),
      start: info.running("start.js"),
      reset: info.running("reset.js")
    }

    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Installing",
        href: "install.js"
      }]
    }

    if (running.start) {
      return [{
        default: true,
        icon: "fa-solid fa-terminal",
        text: "Running Probe",
        href: "start.js"
      }]
    }

    if (running.reset) {
      return [{
        default: true,
        icon: "fa-solid fa-terminal",
        text: "Resetting",
        href: "reset.js"
      }]
    }

    if (installed) {
      return [{
        default: true,
        icon: "fa-solid fa-play",
        text: "Run Probe",
        href: "start.js"
      }, {
        icon: "fa-solid fa-plug",
        text: "Reinstall / Verify",
        href: "install.js"
      }, {
        icon: "fa-regular fa-circle-xmark",
        text: "Reset Venv",
        href: "reset.js",
        confirm: "Remove app/env?"
      }]
    }

    return [{
      default: true,
      icon: "fa-solid fa-plug",
      text: "Install",
      href: "install.js"
    }]
  }
}
