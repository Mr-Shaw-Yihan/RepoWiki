import { createServer } from "node:http";
import { buildApp } from "./app.js";
import { PORT } from "./settings.js";

const app = buildApp();
const server = createServer(app);

server.listen(PORT, () => {
  console.log(`relayboard listening on :${PORT}`);
});

process.on("SIGTERM", () => server.close(() => process.exit(0)));
