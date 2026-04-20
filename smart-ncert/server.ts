import { spawn } from "child_process";
import path from "path";

const pythonProcess = spawn("python3", ["app.py"], {
  stdio: "inherit",
  env: { ...process.env, PYTHONUNBUFFERED: "1" }
});

pythonProcess.on("close", (code) => {
  console.log(`Flask process exited with code ${code}`);
  process.exit(code || 0);
});

process.on("SIGINT", () => {
  pythonProcess.kill("SIGINT");
});

process.on("SIGTERM", () => {
  pythonProcess.kill("SIGTERM");
});
