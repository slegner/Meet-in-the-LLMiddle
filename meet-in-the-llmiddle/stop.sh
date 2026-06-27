#!/usr/bin/env bash
# Stop all Legal Dojo servers (backend + frontend).
echo "Stopping Legal Dojo servers..."
pkill -f "uvicorn main:app" 2>/dev/null && echo "  backend stopped"  || echo "  backend not running"
pkill -f "next dev"        2>/dev/null || true
pkill -f "next-server"     2>/dev/null && echo "  frontend stopped" || echo "  frontend not running"
echo "Done."
