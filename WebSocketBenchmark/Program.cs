using ModbusModule;
using Modbus = ModbusModule.ModbusModule;

var builder = WebApplication.CreateBuilder(args);

var modbusModule = new Modbus();
var pollingService = new PollingService(modbusModule);

pollingService.ValueRecieved += (sequence, value) =>
{
    Console.WriteLine($"[{DateTime.Now:HH:mm:ss.fff}] Sequence: {sequence}, Value: {value}");
};

pollingService.Start();

var app = builder.Build();

app.MapGet("/", () => "Modbus polling is running. Check console for readings.");

app.Lifetime.ApplicationStopping.Register(() =>
{
    Console.WriteLine("Stopping polling service...");
    pollingService.Stop();
});

app.Run();