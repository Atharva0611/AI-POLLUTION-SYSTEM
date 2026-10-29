const ws = new WebSocket("ws://127.0.0.1:9222/devtools/page/6D41E8AAA7162D01F719C174ECA14D29");
let id = 1;
function send(method, params = {}) {
  const msgId = id++;
  return new Promise((resolve) => {
    const handler = (event) => {
      const data = JSON.parse(event.data);
      if (data.id === msgId) {
        ws.removeEventListener("message", handler);
        resolve(data.result);
      }
    };
    ws.addEventListener("message", handler);
    ws.send(JSON.stringify({ id: msgId, method, params }));
  });
}

ws.onopen = async () => {
  await send("Page.reload", { ignoreCache: true });
  await new Promise(r => setTimeout(r, 2500));
  const statusInfo = await send("Runtime.evaluate", {
    expression: "(() => { const chip = document.querySelector('.api-chip'); const statusStrip = document.querySelector('.status-strip'); return { chip: chip ? chip.innerText : null, status: statusStrip ? statusStrip.innerText : null }; })()",
    returnByValue: true
  });
  console.log("Dashboard status after reload:", statusInfo.result.value);

  const ss = await send("Page.captureScreenshot", { format: "png" });
  const fs = await import("fs");
  fs.writeFileSync("C:/final year project/AI-POLLUTION-SYSTEM-GITHUB/dashboard_online.png", Buffer.from(ss.data, "base64"));
  console.log("Saved dashboard_online.png");
  process.exit(0);
};
