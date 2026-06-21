using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

namespace WebSocketBenchmark
{
    public class WebSocketManager
    {
        private readonly ConcurrentDictionary<Guid, WebSocket> sockets = new();

        public async Task HandleConnectionAsync(HttpContext context)
        {
            var socket = await context.WebSockets.AcceptWebSocketAsync();
            var socketId = Guid.NewGuid();
            sockets.TryAdd(socketId, socket);

            var buffer = new byte[1024];

            try
            {
                while (socket.State == WebSocketState.Open)
                {
                    var result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
                    if (result.MessageType == WebSocketMessageType.Close)
                        break;
                }
            }
            catch (WebSocketException)
            {
            }
            finally
            {
                sockets.TryRemove(socketId, out _);
                if (socket.State == WebSocketState.Open)
                {
                    await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closed by server", CancellationToken.None);
                }
            }
        }

        public void Notify(ulong sequence, ushort value, DateTime timeStamp)
        {
            var json = JsonSerializer.Serialize(new { sequence, value, timeStamp });
            var bytes = Encoding.UTF8.GetBytes(json);

            Task.Run(async () =>
            {
                var segment = new ArraySegment<byte>(bytes);

                foreach (var pair in sockets.ToArray())
                {
                    var socket = pair.Value;

                    if (socket.State == WebSocketState.Open)
                    {
                        try
                        {
                            await socket.SendAsync(segment, WebSocketMessageType.Text, true, CancellationToken.None);
                        }
                        catch (Exception ex)
                        {
                            System.Diagnostics.Debug.WriteLine($"Ошибка отправки клиенту {pair.Key}: {ex.Message}");
                            sockets.TryRemove(pair.Key, out _);
                        }
                    }
                }
            });
        }
    }
}