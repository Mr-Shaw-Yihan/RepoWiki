import type { NextFunction, Request, Response } from "express";
import { RATE_LIMIT_PER_MINUTE } from "../settings.js";

const windowMs = 60_000;
const hits = new Map<string, { count: number; resetAt: number }>();

/** Fixed-window per-IP rate limiter; 429s once the window budget is spent. */
export function rateLimit() {
  return (req: Request, res: Response, next: NextFunction) => {
    const now = Date.now();
    const key = req.ip ?? "unknown";
    const slot = hits.get(key) ?? { count: 0, resetAt: now + windowMs };
    if (now > slot.resetAt) {
      slot.count = 0;
      slot.resetAt = now + windowMs;
    }
    slot.count += 1;
    hits.set(key, slot);
    if (slot.count > RATE_LIMIT_PER_MINUTE) {
      res.status(429).json({ error: "rate limit exceeded", retryAfterMs: slot.resetAt - now });
      return;
    }
    next();
  };
}
