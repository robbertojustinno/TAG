"""Company-scoped hierarchical asset category API."""
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

if __package__:
    from .models import AssetCategory, Equipment
else:
    from models import AssetCategory, Equipment

class CategoryPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    parent_id: int | None = Field(default=None, gt=0)
    active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Category name is required')
        return value

class CategoryPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: int | None = Field(default=None, gt=0)
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        return value.strip() if value is not None else value

def slugify(name):
    value = re.sub(r'[^a-z0-9]+', '-', name.lower().encode('ascii', 'ignore').decode()).strip('-')
    return value or 'categoria'

def category_json(category, count=0, children=None):
    return {'id': category.id, 'company_id': category.company_id, 'parent_id': category.parent_id,
            'name': category.name, 'slug': category.slug, 'active': category.active,
            'sort_order': category.sort_order, 'created_at': category.created_at,
            'asset_count': count, **({'children': children} if children is not None else {})}

def build_category_router(auth):
    router = APIRouter()

    def admin(context=Depends(auth.current)):
        if not context.is_superadmin and context.role != 'company_admin':
            raise HTTPException(403, 'Company administrator required')
        return context

    def get_category(db, category_id, company_id):
        category = db.scalar(select(AssetCategory).where(AssetCategory.id == category_id,
                                                          AssetCategory.company_id == company_id))
        if not category:
            raise HTTPException(404, 'Category not found')
        return category

    def validate_parent(db, category_id, parent_id, company_id):
        if parent_id is None:
            return
        parent = get_category(db, parent_id, company_id)
        if category_id is None:
            return
        current = parent
        seen = set()
        while current is not None:
            if current.id in seen or current.id == category_id:
                raise HTTPException(409, 'Category parent would create a cycle')
            seen.add(current.id)
            current = current.parent

    def count_map(db, company_id):
        return dict(db.execute(select(Equipment.category_id, func.count(Equipment.id))
                               .where(Equipment.company_id == company_id, Equipment.category_id.is_not(None))
                               .group_by(Equipment.category_id)).all())

    def ensure_unique(db, company_id, parent_id, slug, exclude_id=None):
        query = select(AssetCategory.id).where(AssetCategory.company_id == company_id,
                                                AssetCategory.slug == slug)
        query = query.where(AssetCategory.parent_id.is_(None) if parent_id is None
                            else AssetCategory.parent_id == parent_id)
        if exclude_id is not None:
            query = query.where(AssetCategory.id != exclude_id)
        if db.scalar(query):
            raise HTTPException(409, 'Category already exists at this level')

    @router.get('/asset-categories')
    def categories(context=Depends(auth.current)):
        with auth.sessions() as db:
            counts = count_map(db, context.company_id)
            return [category_json(c, counts.get(c.id, 0)) for c in db.scalars(
                select(AssetCategory).where(AssetCategory.company_id == context.company_id)
                .order_by(AssetCategory.parent_id, AssetCategory.sort_order, AssetCategory.name, AssetCategory.id))]

    @router.get('/asset-categories/tree')
    def tree(context=Depends(auth.current)):
        with auth.sessions() as db:
            rows = list(db.scalars(select(AssetCategory).where(AssetCategory.company_id == context.company_id)
                                  .order_by(AssetCategory.sort_order, AssetCategory.name, AssetCategory.id)))
            counts = count_map(db, context.company_id)
            by_parent = {}
            for row in rows:
                by_parent.setdefault(row.parent_id, []).append(row)
            def branch(parent_id):
                result = []
                for row in by_parent.get(parent_id, []):
                    children = branch(row.id)
                    result.append(category_json(row, counts.get(row.id, 0) + sum(child['asset_count'] for child in children), children))
                return result
            return branch(None)

    @router.post('/asset-categories', status_code=201)
    def create(payload: CategoryPayload, context=Depends(admin)):
        with auth.sessions() as db:
            validate_parent(db, None, payload.parent_id, context.company_id)
            ensure_unique(db, context.company_id, payload.parent_id, slugify(payload.name))
            category = AssetCategory(company_id=context.company_id, parent_id=payload.parent_id,
                                     name=payload.name, slug=slugify(payload.name), active=payload.active,
                                     sort_order=payload.sort_order)
            db.add(category)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, 'Category already exists at this level') from None
            db.refresh(category)
            return category_json(category)

    @router.patch('/asset-categories/{category_id}')
    def update(category_id: int, payload: CategoryPatch, context=Depends(admin)):
        with auth.sessions() as db:
            category = get_category(db, category_id, context.company_id)
            data = payload.model_dump(exclude_unset=True)
            parent_id = data.get('parent_id', category.parent_id)
            validate_parent(db, category.id, parent_id, context.company_id)
            ensure_unique(db, context.company_id, parent_id,
                          slugify(data.get('name', category.name)), category.id)
            if 'name' in data:
                category.name = data['name']
                category.slug = slugify(data['name'])
            for field in ('parent_id', 'active', 'sort_order'):
                if field in data:
                    setattr(category, field, data[field])
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, 'Category already exists at this level') from None
            db.refresh(category)
            return category_json(category)

    @router.delete('/asset-categories/{category_id}')
    def delete(category_id: int, context=Depends(admin)):
        with auth.sessions() as db:
            category = get_category(db, category_id, context.company_id)
            if db.scalar(select(AssetCategory.id).where(AssetCategory.parent_id == category.id)):
                raise HTTPException(409, 'Category has child categories')
            if db.scalar(select(Equipment.id).where(Equipment.category_id == category.id)):
                raise HTTPException(409, 'Category has assigned assets')
            db.delete(category)
            db.commit()
            return {'ok': True}

    return router
