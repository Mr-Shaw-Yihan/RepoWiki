import express from "express";
import { bearerAuth } from "./middleware/auth.js";
import { rateLimit } from "./middleware/rateLimit.js";
import { boardsRouter } from "./routes/boards.js";
import { cardsRouter } from "./routes/cards.js";

export function buildApp() {
  const app = express();
  app.use(express.json());
  app.use(rateLimit());
  app.use("/api", bearerAuth());
  app.use("/api/boards", boardsRouter());
  app.use("/api/boards/:boardId/cards", cardsRouter());
  app.get("/healthz", (_req, res) => res.json({ ok: true }));
  return app;
}
