from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from .security import AuthContext, current_user
from .services.procurement_provenance import procurement_provenance_matrix


router = APIRouter(prefix="/api/rc15/procurement", tags=["RC15 Procurement"])


@router.get("/provenance-matrix")
def provenance_matrix(ctx: AuthContext = Depends(current_user)) -> dict[str, Any]:
    matrix = procurement_provenance_matrix()
    return {
        **matrix,
        "tenant_id": ctx.tenant_id,
    }
