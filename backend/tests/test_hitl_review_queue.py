from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.db.repositories.human_decision import (
    HumanDecisionRepository,
)


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class FakeResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return FakeScalarResult(
            self._values
        )


class FakeSession:
    def __init__(self, values):
        self.values = values

    async def execute(self, statement):
        return FakeResult(
            self.values
        )


@pytest.mark.asyncio
async def test_list_pending_returns_pending_decisions():
    first = type(
        "Decision",
        (),
        {
            "id": uuid4(),
            "execution_id": uuid4(),
            "status": "pending",
            "created_at": datetime.now(
                timezone.utc
            ),
        },
    )()

    second = type(
        "Decision",
        (),
        {
            "id": uuid4(),
            "execution_id": uuid4(),
            "status": "pending",
            "created_at": datetime.now(
                timezone.utc
            ),
        },
    )()

    session = FakeSession(
        [
            first,
            second,
        ]
    )

    repository = HumanDecisionRepository(
        session
    )

    result = await repository.list_pending(
        limit=50
    )

    assert result == [
        first,
        second,
    ]


@pytest.mark.asyncio
async def test_list_pending_rejects_invalid_limit():
    session = FakeSession([])

    repository = HumanDecisionRepository(
        session
    )

    with pytest.raises(ValueError):
        await repository.list_pending(
            limit=0
        )