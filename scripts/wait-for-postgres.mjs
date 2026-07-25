import net from "node:net";

const host = process.env.POSTGRES_HOST ?? "127.0.0.1";
const port = Number(process.env.POSTGRES_PORT ?? "5432");
const timeoutMs = Number(process.env.POSTGRES_WAIT_TIMEOUT_MS ?? "60000");
const intervalMs = 500;

function tryConnect() {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host, port }, () => {
      socket.end();
      resolve(true);
    });
    socket.on("error", reject);
  });
}

const started = Date.now();

while (Date.now() - started < timeoutMs) {
  try {
    await tryConnect();
    console.log(`Postgres ready at ${host}:${port}`);
    process.exit(0);
  } catch {
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

console.error(`Timed out waiting for Postgres at ${host}:${port}`);
process.exit(1);
