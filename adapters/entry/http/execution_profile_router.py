from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from adapters.entry.http.deps import get_db
from adapters.entry.http.dtos.trade_execution_dtos import (
    ExecutionProfileOutDTO,
    ExecutionProfileQuoteHistoryOutDTO,
    ExecutionProfileUpsertDTO,
    TradePaginationDTO,
)
from adapters.external.binance.binance_futures_client import BinanceFuturesClient
from adapters.external.database.execution_profile_quote_history_repository_mongodb import (
    ExecutionProfileQuoteHistoryRepositoryMongoDB,
)
from adapters.external.database.execution_profile_repository_mongodb import (
    ExecutionProfileRepositoryMongoDB,
)
from adapters.external.database.trade_order_repository_mongodb import TradeOrderRepositoryMongoDB
from adapters.external.database.trade_position_repository_mongodb import (
    TradePositionRepositoryMongoDB,
)
from core.usecases.trade_execution_use_case import TradeExecutionUseCase


router = APIRouter(prefix="/execution-profiles", tags=["execution-profiles"])


def get_use_case(db: AsyncIOMotorDatabase, binance_client: BinanceFuturesClient) -> TradeExecutionUseCase:
    """
    Build the trade execution use case.
    """
    return TradeExecutionUseCase(
        profile_repo=ExecutionProfileRepositoryMongoDB(db),
        profile_quote_history_repo=ExecutionProfileQuoteHistoryRepositoryMongoDB(db),
        position_repo=TradePositionRepositoryMongoDB(db),
        order_repo=TradeOrderRepositoryMongoDB(db),
        binance_client=binance_client,
    )


@router.post("/upsert", response_model=dict)
async def upsert_execution_profile(
    body: ExecutionProfileUpsertDTO,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Create or update an execution profile.
    """
    try:
        uc = get_use_case(db, request.app.state.binance_futures_client)
        await uc.ensure_indexes()

        ent = await uc.upsert_execution_profile(
            execution_account_id=body.execution_account_id,
            symbol=body.symbol,
            is_enabled=body.is_enabled,
            quote_size_usd=body.quote_size_usd,
            leverage=body.leverage,
        )
        data = ExecutionProfileOutDTO.model_validate(ent.model_dump())
        return {"ok": True, "message": "ok", "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to upsert execution profile: {exc}") from exc


@router.get("", response_model=dict)
async def list_execution_profiles(
    request: Request,
    execution_account_id: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List execution profiles.
    """
    try:
        uc = get_use_case(db, request.app.state.binance_futures_client)
        await uc.ensure_indexes()

        items = await uc.list_execution_profiles(execution_account_id=execution_account_id)
        data = [ExecutionProfileOutDTO.model_validate(item.model_dump()) for item in items]
        return {"ok": True, "message": "ok", "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list execution profiles: {exc}") from exc


@router.get("/quote-history", response_model=dict)
async def list_execution_profile_quote_history(
    request: Request,
    execution_account_id: str = Query(..., min_length=1),
    symbol: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=5000),
    page: int | None = Query(None, ge=1),
    offset: int | None = Query(None, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List quote-size change history for one execution profile.
    """
    try:
        uc = get_use_case(db, request.app.state.binance_futures_client)
        await uc.ensure_indexes()

        result = await uc.list_quote_history_paginated(
            execution_account_id=execution_account_id,
            symbol=symbol,
            limit=int(limit),
            page=page,
            offset=offset,
        )

        data = [
            ExecutionProfileQuoteHistoryOutDTO.model_validate(item.model_dump())
            for item in result["items"]
        ]
        pagination = TradePaginationDTO.model_validate(result["pagination"])

        return {
            "ok": True,
            "message": "ok",
            "data": data,
            "pagination": pagination,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list execution profile quote history: {exc}") from exc