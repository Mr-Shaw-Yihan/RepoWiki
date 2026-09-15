import { Router } from "express";
import { db } from "../db.js";

export function boardsRouter() {
  const router = Router({ mergeParams: true });

  router.get("/", (_req, res) => {
    res.json({ boards: db.listBoards() });
  });

  router.post("/", (req, res) => {
    const name = String(req.body?.name ?? "").trim();
    if (!name) {
      res.status(400).json({ error: "name is required" });
      return;
    }
    res.status(201).json(db.createBoard(name));
  });

  router.get("/:boardId", (req, res) => {
    const board = db.getBoard(req.params.boardId);
    if (!board) {
      res.status(404).json({ error: "board not found" });
      return;
    }
    res.json(board);
  });

  return router;
}
