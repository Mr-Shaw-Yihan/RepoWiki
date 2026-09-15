import type { NextFunction, Request, Response } from "express";
import { AUTH_TOKEN } from "../settings.js";

/** Require an `Authorization: Bearer <token>` header on every routed request. */
export function bearerAuth() {
  return (req: Request, res: Response, next: NextFunction) => {
    const header = req.header("authorization") ?? "";
    const [scheme, token] = header.split(" ");
    if (scheme.toLowerCase() !== "bearer" || token !== AUTH_TOKEN) {
      res.status(401).json({ error: "missing or invalid bearer token" });
      return;
    }
    next();
  };
}
