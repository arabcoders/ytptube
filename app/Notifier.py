from socketio import AsyncServer
from Utils import ObjectSerializer


class Notifier:
    def __init__(self, sio: AsyncServer, serializer: ObjectSerializer):
        self.sio = sio
        self.serializer = serializer

    async def added(self, dl):
        await self.emit('added', dl)

    async def updated(self, dl):
        await self.emit('updated', dl)

    async def completed(self, dl):
        await self.emit('completed', dl)

    async def canceled(self, id):
        await self.emit('canceled', id)

    async def cleared(self, id):
        await self.emit('cleared', id)

    async def emit(self, event: str, data):
        await self.sio.emit(event, self.serializer.encode(data))
