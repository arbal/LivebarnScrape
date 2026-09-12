#!/bin/bash
set -e

APP_VERSION="$(cat /app/VERSION 2>/dev/null || echo dev)"

echo "=========================================="
echo " LiveBarn Manager v${APP_VERSION} - Docker Startup"
echo "=========================================="
echo ""

# Environment credentials are optional because they can be saved from the admin UI.
if [ -z "$LIVEBARN_EMAIL" ] || [ -z "$LIVEBARN_PASSWORD" ]; then
    echo "⚠️  LiveBarn environment credentials are not set"
    echo "   Configure them from the admin page or set LIVEBARN_EMAIL and LIVEBARN_PASSWORD"
    echo ""
else
    echo "✅ Environment credentials configured"
    echo ""
fi

# Check the database with Python's stdlib sqlite3; the base image does not
# need the unrelated sqlite3 command-line package for this read-only check.
DB_PATH="${DB_PATH:-/data/livebarn.db}"
DB_STATE="$(python startup_db.py "$DB_PATH" 2>/dev/null)" || DB_STATE="query-error"
DB_HAS_DATA=false

if [ "${DB_STATE%% *}" = "populated" ]; then
    DB_HAS_DATA=true
    VENUE_COUNT="${DB_STATE#* }"
    echo "✅ Database found at /data/livebarn.db"
    echo "   📊 Contains $VENUE_COUNT venues"
    echo ""
elif [ "${DB_STATE%% *}" = "query-error" ]; then
    echo "❌ Database query failed; refusing to rebuild or overwrite persisted state"
    exit 1
    echo ""
fi

# Auto-build catalog if needed
if [ "$DB_HAS_DATA" = false ]; then
    echo "🔨 Building venue catalog (first-time setup)..."
    echo "   This may take 1-2 minutes..."
    echo ""
    
    if python build_catalog.py; then
        echo ""
        echo "✅ Catalog build complete!"
        echo ""
    else
        echo ""
        echo "❌ Catalog build failed!"
        echo "   You can rebuild manually with:"
        echo "   docker exec livebarn-manager python build_catalog.py"
        echo ""
        echo "   Continuing startup anyway..."
        echo ""
    fi
fi

# Start the manager
echo "🚀 Starting LiveBarn Manager v${APP_VERSION}..."
echo ""
exec python livebarn_manager.py
