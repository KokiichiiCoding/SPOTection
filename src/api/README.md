# Spotection API

FastAPI-based REST API for parking detection.

## Running

```bash
python main.py serve
```

## Endpoints

- `GET /api/lots/{lot_id}/status` - Get parking status
- `GET /api/lots/{lot_id}/image` - Get annotated image
- `WS /ws` - WebSocket for live updates

See `/docs` for interactive API documentation.
