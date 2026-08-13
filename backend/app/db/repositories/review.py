from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.review import ReviewModel
from app.schemas.review import ReviewResult


class ReviewRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def create(
        self,
        *,
        execution_id: UUID,
        review: ReviewResult,
        review_id: UUID | None = None,
    ) -> ReviewModel:
        model = ReviewModel(
            id=review_id or uuid4(),
            execution_id=execution_id,
            approved=review.approved,
            quality_score=review.quality_score,
            confidence=review.confidence,
            feedback=review.feedback,
            issues=review.issues,
        )

        self.session.add(model)

        await self.session.flush()

        return model

    async def get(
        self,
        review_id: UUID,
    ) -> ReviewModel | None:
        result = await self.session.execute(
            select(ReviewModel).where(
                ReviewModel.id == review_id
            )
        )

        return result.scalar_one_or_none()

    async def get_for_execution(
        self,
        execution_id: UUID,
    ) -> list[ReviewModel]:
        result = await self.session.execute(
            select(ReviewModel)
            .where(
                ReviewModel.execution_id
                == execution_id
            )
            .order_by(
                ReviewModel.created_at
            )
        )

        return list(result.scalars().all())