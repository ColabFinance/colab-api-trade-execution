from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from adapters.entry.http.deps import get_db
from adapters.entry.http.dtos.trade_execution_dtos import (
    TradeCloseRequestDTO,
    TradeExecutionResponseDTO,
    TradeOpenRequestDTO,
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
        print("\n open result",result)
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
        print("\n close result",result)
        return TradeExecutionResponseDTO(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to close trade position: {exc}") from exc


@router.get("/positions/active", response_model=dict)
async def list_active_trade_positions(
    request: Request,
    execution_account_id: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List active trade positions.
    """
    try:
        uc = get_use_case(request, db)
        await uc.ensure_indexes()

        items = await uc.list_active_positions(execution_account_id=execution_account_id)
        data = [item.model_dump() for item in items]
        return {"ok": True, "message": "ok", "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list active positions: {exc}") from exc


@router.get("/orders", response_model=dict)
async def list_trade_orders_by_strategy(
    request: Request,
    strategy_id: str = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List trade order history for one strategy.
    """
    try:
        uc = get_use_case(request, db)
        await uc.ensure_indexes()

        items = await uc.list_orders_by_strategy_id(strategy_id=strategy_id, limit=int(limit))
        data = [item.model_dump() for item in items]
        return {"ok": True, "message": "ok", "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list trade orders: {exc}") from exc