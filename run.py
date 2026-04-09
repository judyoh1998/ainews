import os

import uvicorn

from app.config import settings

if __name__ == "__main__":
    # Railway injects PORT env var
    port = int(os.environ.get("PORT", settings.port))
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=port,
        reload=settings.debug,
    )
