#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8742

# Kill anything on that port
lsof -ti tcp:$PORT | xargs kill -9 2>/dev/null
sleep 0.3

# Start proxy server
cd "$DIR"
python3 server.py &
SERVER_PID=$!

# Wait until ready
for i in {1..15}; do
  curl -sf "http://127.0.0.1:$PORT/index.html" &>/dev/null && break
  sleep 0.3
done

# Open in browser
open "http://127.0.0.1:$PORT/index.html"

echo ""
echo "✅ MixCheck AI is running at http://127.0.0.1:$PORT"
echo "   Keep this window open while using the app."
echo "   Press Ctrl+C to stop the server."

wait $SERVER_PID
