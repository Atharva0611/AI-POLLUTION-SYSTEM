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

const logs = [];
ws.onopen = async () => {
  ws.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    if (data.method === "Console.messageAdded") logs.push(data.params.message);
    if (data.method === "Runtime.exceptionThrown") logs.push(data.params.exceptionDetails);
  });

  await send("Console.enable");
  await send("Runtime.enable");

  const dom = await send("Runtime.evaluate", {
    expression: "({ body: document.body.innerHTML, url: window.location.href, title: document.title })",
    returnByValue: true
  });
  console.log("DOM:", dom.result.value);
  console.log("Logs:", logs);

  process.exit(0);
};
