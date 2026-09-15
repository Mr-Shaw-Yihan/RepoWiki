from taskvane.models import Task
from taskvane.storage import TaskStore


def test_add_and_list_round_trip(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    store.add(Task(title="write docs", priority="high"))
    store.add(Task(title="ship it"))
    open_tasks = store.list(open_only=True)
    assert [t.title for t in open_tasks] == ["write docs", "ship it"]
    store.mark_done(1)
    assert [t.title for t in store.list(open_only=True)] == ["ship it"]
