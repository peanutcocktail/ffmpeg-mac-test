module.exports = {
  run: [{
    method: "shell.run",
    params: {
      venv: "env",
      venv_python: "3.12",
      path: "app",
      message: [
        "python ffmpeg_probe.py --wait --require"
      ]
    }
  }]
}
