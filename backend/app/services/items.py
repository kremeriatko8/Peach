import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item
from app.schemas import ItemCreate, ItemUpdate


async def list_items(
    session: AsyncSession, *, owner_id: str, limit: int, offset: int
) -> tuple[list[Item], int]:
    total = (
        await session.scalar(
            select(func.count()).select_from(Item).where(Item.owner_id == owner_id)
        )
        or 0
    )
    result = await session.execute(
        select(Item)
        .where(Item.owner_id == owner_id)
        .order_by(Item.created_at.desc(), Item.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars()), total


async def get_item(session: AsyncSession, item_id: uuid.UUID, *, owner_id: str) -> Item | None:
    return await session.scalar(select(Item).where(Item.id == item_id, Item.owner_id == owner_id))


async def create_item(session: AsyncSession, payload: ItemCreate, *, owner_id: str) -> Item:
    item = Item(**payload.model_dump(), owner_id=owner_id)
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return item


async def update_item(session: AsyncSession, item: Item, payload: ItemUpdate) -> Item:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await session.flush()
    await session.refresh(item)
    return item


async def delete_item(session: AsyncSession, item: Item) -> None:
    await session.delete(item)
    await session.flush()
