from uuid import uuid4

from app.tasks.execution import execute_agentflow_task


def test_celery_task_is_registered():
    assert (
        execute_agentflow_task.name
        == "agentflow.execute_task"
    )


def test_celery_task_runs():
    result = execute_agentflow_task.apply(
        kwargs={
            "task_id": str(uuid4()),
            "execution_id": str(uuid4()),
            "user_id": "user-123",
            "description": "Test task",
        }
    )

    assert result.successful()