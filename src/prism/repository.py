from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prism.models import Comment, Review


class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.db = session

    async def create_review(self, repo: str, pr_number: int, diff_type: str, reasoning: str) -> Review:
        review = Review(
            repo=repo,
            pr_number=pr_number,
            diff_type=diff_type,
            reasoning=reasoning,
        )
        self.db.add(review)
        await self.db.commit()
        await self.db.refresh(review)
        return review

    async def create_comment(self, review_id: int, filename: str, line: int, comment: str, severity: str) -> Comment:
        persist_comment = Comment(
            review_id=review_id,
            filename=filename,
            line=line,
            comment=comment,
            severity=severity,
        )
        self.db.add(persist_comment)  # stage the object
        await self.db.commit()  # write to database
        await self.db.refresh(persist_comment)  # populates auto-generated fields like id
        return persist_comment

    async def get_review(self, repo: str, pr_number: int) -> Review | None:
        result = await self.db.execute(
            select(Review).where(Review.repo == repo, Review.pr_number == pr_number)
        )
        return result.scalar_one_or_none()
