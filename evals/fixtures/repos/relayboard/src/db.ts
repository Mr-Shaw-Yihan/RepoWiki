export interface Card {
  id: string;
  title: string;
  column: string;
}

export interface Board {
  id: string;
  name: string;
  cards: Card[];
}

/** Process-local store: a map of boards, no persistence, restart wipes it. */
class InMemoryDb {
  private boards = new Map<string, Board>();
  private seq = 0;

  private nextId(prefix: string) {
    this.seq += 1;
    return `${prefix}_${this.seq}`;
  }

  listBoards(): Board[] {
    return [...this.boards.values()];
  }

  createBoard(name: string): Board {
    const board: Board = { id: this.nextId("b"), name, cards: [] };
    this.boards.set(board.id, board);
    return board;
  }

  getBoard(id: string): Board | undefined {
    return this.boards.get(id);
  }

  addCard(boardId: string, title: string, column: string): Card {
    const card: Card = { id: this.nextId("c"), title, column };
    this.boards.get(boardId)!.cards.push(card);
    return card;
  }

  moveCard(boardId: string, cardId: string, column: string): Card | undefined {
    const card = this.boards.get(boardId)?.cards.find((c) => c.id === cardId);
    if (card) card.column = column;
    return card;
  }
}

export const db = new InMemoryDb();
