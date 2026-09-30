"""Fase 1 category hierarchy and additive, repeatable migration."""
import re
import unicodedata
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


def slugify(name):
    clean = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', clean).strip('-') or name.lower()



def category_path(category):
    names = []
    while category:
        names.append(category.name)
        category = category.parent
    return ' / '.join(reversed(names))


def validate_category(db, model, identifier):
    if identifier is not None and db.get(model, identifier) is None:
        raise HTTPException(422, 'Categoria não encontrada.')


def category_ids(db, model, identifier, include_children=True):
    validate_category(db, model, identifier)
    ids = {identifier}
    if include_children:
        rows = db.query(model).all()
        while True:
            descendants = {r.id for r in rows if r.parent_id in ids}
            if descendants <= ids:
                break
            ids.update(descendants)
    return ids


class CategoryPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: int | None = Field(None, gt=0)
    active: bool = True
    sort_order: int = 0

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('Informe o nome da categoria.')
        return value.strip()


class CategoryPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    parent_id: int | None = Field(None, gt=0)
    active: bool | None = None
    sort_order: int | None = None

    @field_validator('name', 'active', 'sort_order')
    @classmethod
    def no_null(cls, value):
        if value is None or isinstance(value, str) and not value.strip():
            raise ValueError('Valor obrigatório quando informado.')
        return value.strip() if isinstance(value, str) else value


def build_category_router(sessions, model, equipment, require_admin):
    router = APIRouter(prefix='/asset-categories')

    def serialized(row):
        return {key:getattr(row,key) for key in ('id','name','slug','parent_id','active','sort_order')}

    def rows(tree=False):
        with sessions() as db:
            categories = db.query(model).order_by(model.sort_order, model.name, model.id).all()
            nodes = {row.id:{**serialized(row), 'asset_count':0, 'children':[]} for row in categories}
            for asset in db.query(equipment).filter(equipment.category_id.isnot(None)):
                if asset.category_id in nodes:
                    nodes[asset.category_id]['asset_count'] += 1
            roots = []
            for row in categories:
                if row.parent_id in nodes:
                    nodes[row.parent_id]['children'].append(nodes[row.id])
                else:
                    roots.append(nodes[row.id])
            def count(node):
                node['asset_count'] += sum(count(child) for child in node['children'])
                return node['asset_count']
            for node in roots:
                count(node)
            return roots if tree else [{k:v for k,v in node.items() if k!='children'} for node in nodes.values()]

    @router.get('')
    def listing():
        return rows()

    @router.get('/tree')
    def tree():
        return rows(True)

    def save(db, row, values):
        parent_id = values.get('parent_id', row.parent_id)
        validate_category(db, model, parent_id)
        parent = db.get(model, parent_id) if parent_id else None
        while parent:
            if parent.id == row.id:
                raise HTTPException(422, 'Uma categoria não pode ser filha de si mesma ou de seus descendentes.')
            parent = parent.parent
        for key,value in values.items():
            setattr(row,key,value)
        row.slug = slugify(row.name)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Já existe uma categoria com esse nome neste ramo.')
        db.refresh(row)
        return serialized(row)

    @router.post('', status_code=201, dependencies=[Depends(require_admin)])
    def create(payload: CategoryPayload):
        with sessions() as db:
            return save(db, model(), payload.model_dump())

    @router.patch('/{identifier}', dependencies=[Depends(require_admin)])
    def update(identifier: int, payload: CategoryPatch):
        with sessions() as db:
            row = db.get(model, identifier)
            if not row:
                raise HTTPException(404, 'Categoria não encontrada.')
            return save(db, row, payload.model_dump(exclude_unset=True))

    @router.delete('/{identifier}', dependencies=[Depends(require_admin)])
    def delete(identifier: int):
        with sessions() as db:
            row = db.get(model, identifier)
            if not row:
                raise HTTPException(404, 'Categoria não encontrada.')
            if db.query(model).filter(model.parent_id==identifier).first() or db.query(equipment).filter(equipment.category_id==identifier).first():
                raise HTTPException(409, 'Remova as subcategorias e desvincule os ativos antes de excluir.')
            db.delete(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, 'A categoria está em uso.')
            return {'ok':True}

    return router
