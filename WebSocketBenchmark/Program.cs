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

            var modbusModule = new Modbus();
            var pollingService = new PollingService(modbusModule);
            pollingService.Start();
            pollingService.ValueChanged += longPollingManager.Notify;

            var app = builder.Build();

            app.MapGet("/api/shortPolling", () =>
            {
                return Results.Ok(new
                {
                    pollingService.Sequence,
                    Value = pollingService.LastValue,
                    Timestamp = pollingService.GenerateLastTime
                });
            });

            app.MapGet("/api/longPolling", async (ulong lastSequence, CancellationToken cancellationToken) =>
            {
                if (pollingService.Sequence > lastSequence)
                {
                    return Results.Ok(new
                    {
                        pollingService.Sequence,
                        Value = pollingService.LastValue,
                        Timestamp = pollingService.GenerateLastTime
                    });
                }

                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));

                using var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, timeout.Token);

                try
                {
                    var (Sequence, Value, Timestamp) = await longPollingManager.WaitForUpdateAsync(linked.Token);

                    return Results.Ok(new
                    {
                        Sequence,
                        Value,
                        Timestamp
                    });
                }
                catch (TaskCanceledException)
                {
                    return Results.NoContent();
                }
            });

            app.Lifetime.ApplicationStopping.Register(pollingService.Stop);
            app.Run();
        }
    }
}