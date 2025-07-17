import asyncio
import websockets

connected = set()

async def handler(websocket):
    connected.add(websocket)
    print(f"[WebSocket] 新前端连接: {websocket.remote_address}")
    try:
        async for message in websocket:
            print(f"[WebSocket] 收到前端消息: {message}")
            # 收到消息后广播给所有前端
            await broadcast(f"前端消息: {message}")
    except Exception as e:
        print(f"[WebSocket] 连接异常: {e}")
    finally:
        connected.remove(websocket)
        print(f"[WebSocket] 前端断开: {websocket.remote_address}")

async def broadcast(message):
    if connected:
        await asyncio.wait([ws.send(message) for ws in connected])

async def main():
    async with websockets.serve(handler, "0.0.0.0", 6789):
        print("[WebSocket] 服务端启动 ws://0.0.0.0:6789")
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main()) 