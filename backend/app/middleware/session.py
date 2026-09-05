import uuid
import logging
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import select, update

from app.db import async_session_factory
from app.models import SessionModel

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Allow CORS preflight requests without DB interaction
        if request.method == "OPTIONS":
            return await call_next(request)

        session_id_header = request.headers.get("X-Session-Id")
        resolved_session_id: uuid.UUID = None
        now = datetime.now(timezone.utc)

        async with async_session_factory() as db:
            if session_id_header:
                try:
                    parsed_uuid = uuid.UUID(session_id_header.strip())
                    # Check if session exists in DB
                    stmt = select(SessionModel).where(SessionModel.session_id == parsed_uuid)
                    result = await db.execute(stmt)
                    session_row = result.scalar_one_or_none()

                    if session_row:
                        resolved_session_id = parsed_uuid
                        # Update last_active_at
                        await db.execute(
                            update(SessionModel)
                            .where(SessionModel.session_id == parsed_uuid)
                            .values(last_active_at=now)
                        )
                        await db.commit()
                except (ValueError, TypeError):
                    logger.debug(f"Invalid UUID in X-Session-Id header: {session_id_header}")

            # If no valid session, create a new one
            if not resolved_session_id:
                new_session_id = uuid.uuid4()
                new_session = SessionModel(
                    session_id=new_session_id,
                    created_at=now,
                    last_active_at=now
                )
                db.add(new_session)
                await db.commit()
                resolved_session_id = new_session_id

        # Attach resolved session_id to request state
        request.state.session_id = resolved_session_id

        response = await call_next(request)

        # Attach X-Session-Id header to response
        response.headers["X-Session-Id"] = str(resolved_session_id)
        
        # Ensure CORS exposes X-Session-Id
        existing_exposed = response.headers.get("Access-Control-Expose-Headers", "")
        if existing_exposed:
            if "X-Session-Id" not in existing_exposed:
                response.headers["Access-Control-Expose-Headers"] = f"{existing_exposed}, X-Session-Id"
        else:
            response.headers["Access-Control-Expose-Headers"] = "X-Session-Id"

        return response
