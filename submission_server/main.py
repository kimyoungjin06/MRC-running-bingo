from __future__ import annotations

from mrc_submit.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=app.state.settings.host, port=app.state.settings.port, reload=False)
