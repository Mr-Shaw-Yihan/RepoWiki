import { Router } from "express";
import { db } from "../db.js";

export function cardsRouter() {
  const router = Router({ mergeParams: true });

  router.post("/", (req, res) => {
    const board = db.getBoard(req.params.boardId);
    if (!board) {
      res.status(404).json({ error: "board not found" });
      return;
    }
    const title = String(req.body?.title ?? "").trim();
    if (!title) {
      res.status(400).json({ error: "title is required" });
      return;
    }
    const card = db.addCard(board.id, title, req.body?.column ?? "todo");
    res.status(201).json(card);
  });

  router.patch("/:cardId/move", (req, res) => {
    const column = String(req.body?.column ?? "");
    const card = db.moveCard(req.params.boardId, req.params.cardId, column);
    if (!card) {
      res.status(404).json({ error: "card not found" });
      return;
    }
    res.json(card);
  });

  return router;
}
