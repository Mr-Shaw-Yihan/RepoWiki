export const PORT = Number(process.env.PORT ?? 4317);
export const AUTH_TOKEN = process.env.RELAYBOARD_TOKEN ?? "dev-token";
export const RATE_LIMIT_PER_MINUTE = Number(process.env.RATE_LIMIT_PER_MINUTE ?? 120);
