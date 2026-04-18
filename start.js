module.exports = {
  run: [{
    method: "shell.run",
    params: {
      venv: "env",
      path: "app",
      message: [
        "python ffmpeg_probe.py"
      ]
    }
  }]
}
