from uuid import uuid4

from app.db.base import Base
from app.db.models import (
    ExecutionModel,
    ReviewModel,
    SubTaskModel,
    TaskModel,
)


def test_postgres_models_are_registered():
    tables = Base.metadata.tables

    assert "tasks" in tables
    assert "executions" in tables
    assert "subtasks" in tables
    assert "reviews" in tables
    assert "subtask_dependencies" in tables


def test_task_model_has_expected_columns():
    columns = TaskModel.__table__.columns

    assert "id" in columns
    assert "user_id" in columns
    assert "description" in columns
    assert "created_at" in columns


def test_execution_model_has_expected_columns():
    columns = ExecutionModel.__table__.columns

    assert "id" in columns
    assert "task_id" in columns
    assert "status" in columns


def test_subtask_model_has_expected_columns():
    columns = SubTaskModel.__table__.columns

    assert "id" in columns
    assert "execution_id" in columns
    assert "description" in columns
    assert "assigned_specialist" in columns
    assert "required_inputs" in columns
    assert "expected_output" in columns
    assert "estimated_complexity" in columns


def test_review_model_has_expected_columns():
    columns = ReviewModel.__table__.columns

    assert "id" in columns
    assert "execution_id" in columns
    assert "approved" in columns
    assert "quality_score" in columns
    assert "confidence" in columns
    assert "feedback" in columns
    assert "issues" in columns