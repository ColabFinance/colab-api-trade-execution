from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from adapters.entry.http.deps import get_db
from adapters.entry.http.dtos.trade_execution_dtos import (
    TradeCloseRequestDTO,
    TradeExecutionResponseDTO,
    TradeOpenRequestDTO,
    TradeOrderListQueryDTO,
    TradeOrderListResponseDTO,
    TradeOrderOutDTO,
    TradePaginationDTO,
    TradePositionListQueryDTO,
    TradePositionListResponseDTO,
    TradePositionOutDTO,
)
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


router = APIRouter(prefix="/trade-execution", tags=["trade-execution"])


def get_use_case(request: Request, db: AsyncIOMotorDatabase) -> TradeExecutionUseCase:
    """
    Build the trade execution use case.
    """
    return TradeExecutionUseCase(
        profile_repo=ExecutionProfileRepositoryMongoDB(db),
        profile_quote_history_repo=ExecutionProfileQuoteHistoryRepositoryMongoDB(db),
        position_repo=TradePositionRepositoryMongoDB(db),
        order_repo=TradeOrderRepositoryMongoDB(db),
        binance_client=request.app.state.binance_futures_client,
    )


@router.post("/open", response_model=TradeExecutionResponseDTO)
async def open_trade_position(
    body: TradeOpenRequestDTO,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Open a new futures market position.
    """
    try:
        uc = get_use_case(request, db)
        await uc.ensure_indexes()

        result = await uc.open_position(
            strategy_id=body.strategy_id,
            execution_account_id=body.execution_account_id,
            symbol=body.symbol,
            position_side=body.position_side,
            signal_id=body.signal_id,
            signal_ts=body.signal_ts,
            signal_type=body.signal_type,
            idempotency_key=body.idempotency_key,
        )
        return TradeExecutionResponseDTO(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to open trade position: {exc}") from exc


@router.post("/close", response_model=TradeExecutionResponseDTO)
async def close_trade_position(
    body: TradeCloseRequestDTO,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Close the active futures position for a strategy/account/symbol.

    After a successful close, the execution profile quote can be automatically
    adjusted based on realized net PnL, and that adjustment is stored in the
    quote-history collection.
    """
    try:
        uc = get_use_case(request, db)
        await uc.ensure_indexes()

        result = await uc.close_position(
            strategy_id=body.strategy_id,
            execution_account_id=body.execution_account_id,
            symbol=body.symbol,
            close_reason=body.close_reason,
            signal_id=body.signal_id,
            signal_ts=body.signal_ts,
            idempotency_key=body.idempotency_key,
        )
        return TradeExecutionResponseDTO(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to close trade position: {exc}") from exc


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
    List dynamic quote adjustment history for one execution profile.
    """
    try:
        uc = get_use_case(request, db)
        await uc.ensure_indexes()

        result = await uc.list_quote_history_paginated(
            execution_account_id=execution_account_id,
            symbol=symbol,
            limit=int(limit),
            page=page,
            offset=offset,
        )

        data = [item.model_dump(mode="python") for item in result["items"]]

        return {
            "ok": True,
            "message": "ok",
            "data": data,
            "pagination": result["pagination"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list quote history: {exc}") from exc


@router.get("/positions/active", response_model=TradePositionListResponseDTO)
async def list_active_trade_positions(
    request: Request,
    query: TradePositionListQueryDTO = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List positions with pagination and status scope support.

    The route path is preserved for compatibility.
    """
    try:
        uc = get_use_case(request, db)
        await uc.ensure_indexes()

        result = await uc.list_positions_paginated(
            execution_account_id=query.execution_account_id,
            status_scope=query.status_scope,
            limit=int(query.limit),
            page=query.page,
            offset=query.offset,
        )
        data = [TradePositionOutDTO.model_validate(item.model_dump()) for item in result["items"]]
        pagination = TradePaginationDTO.model_validate(result["pagination"])

        return TradePositionListResponseDTO(
            ok=True,
            message="ok",
            data=data,
            pagination=pagination,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list positions: {exc}") from exc


@router.get("/orders", response_model=TradeOrderListResponseDTO)
async def list_trade_orders_by_strategy(
    request: Request,
    query: TradeOrderListQueryDTO = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List trade order history with pagination and lifecycle scope support.
    """
    try:
        uc = get_use_case(request, db)
        await uc.ensure_indexes()

        result = await uc.list_orders_paginated(
            strategy_id=query.strategy_id,
            execution_account_id=query.execution_account_id,
            lifecycle_scope=query.lifecycle_scope,
            limit=int(query.limit),
            page=query.page,
            offset=query.offset,
        )
        data = [TradeOrderOutDTO.model_validate(item.model_dump()) for item in result["items"]]
        pagination = TradePaginationDTO.model_validate(result["pagination"])

        return TradeOrderListResponseDTO(
            ok=True,
            message="ok",
            data=data,
            pagination=pagination,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list trade orders: {exc}") from exc