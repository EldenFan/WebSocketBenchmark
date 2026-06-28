using ModbusModule;
using Modbus = ModbusModule.ModbusModule;

namespace WebSocketBenchmark
{
    public class Program
    {
        public static void Main(string[] args)
        {
            var builder = WebApplication.CreateBuilder(args);
            builder.WebHost.UseUrls("http://*:5000");

            var longPollingManager = new LongPollingService();
            var webSocketManager = new WebSocketManager();

            var modbusModule = new Modbus();
            var pollingService = new PollingService(modbusModule);
            pollingService.Start();

            pollingService.ValueChanged += longPollingManager.Notify;
            pollingService.ValueChanged += webSocketManager.Notify;

            var app = builder.Build();
            app.UseWebSockets();

            app.MapGet("/api/shortPolling", () =>
            {
                return Results.Ok(new
                {
                    pollingService.Sequence,
                    Value = pollingService.LastValue,
                    TimeStamp = pollingService.GenerateLastTime
                });
            });

            app.MapGet("/api/longPolling", async (ulong lastSequence, CancellationToken cancellationToken) =>
            {
                ulong nextSequence = lastSequence + 1;

                if (pollingService.Sequence >= nextSequence)
                {
                    if (pollingService.TryGetState(nextSequence, out var value, out var timestamp))
                    {
                        return Results.Ok(new { Sequence = nextSequence, Value = value, Timestamp = timestamp });
                    }

                    return Results.Ok(new
                    {
                        pollingService.Sequence,
                        Value = pollingService.LastValue,
                        TimeStamp = pollingService.GenerateLastTime
                    });
                }

                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(60));
                using var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, timeout.Token);

                try
                {
                    var (sequence, val, ts) = await longPollingManager.WaitForUpdateAsync(linked.Token);

                    return Results.Ok(new { Sequence = sequence, Value = val, TimeStamp = ts });
                }
                catch (TaskCanceledException)
                {
                    return Results.NoContent();
                }
            });

            app.Map("/api/ws", async context =>
            {
                if (context.WebSockets.IsWebSocketRequest)
                {
                    await webSocketManager.HandleConnectionAsync(context);
                }
                else
                {
                    context.Response.StatusCode = StatusCodes.Status400BadRequest;
                }
            });

            app.Lifetime.ApplicationStopping.Register(pollingService.Stop);
            app.Run();
        }
    }
}