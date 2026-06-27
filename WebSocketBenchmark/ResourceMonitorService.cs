using System.Diagnostics;

public class ResourceMonitorService : BackgroundService
{
    private readonly string filePath = "server_metrics.csv";
    private readonly Process currentProcess;

    public ResourceMonitorService()
    {
        currentProcess = Process.GetCurrentProcess();
        File.WriteAllText(filePath, "Timestamp;CpuUsagePercent;RamUsageMb\n");
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var cpu = GetCpuUsage();
                currentProcess.Refresh();
                var ram = currentProcess.WorkingSet64 / 1024.0 / 1024.0;

                var line = $"{DateTime.Now:HH:mm:ss};{cpu:F2};{ram:F2}\n";
                File.AppendAllText(filePath, line);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Ошибка сбора метрик: {ex.Message}");
            }

            await Task.Delay(1000, stoppingToken);
        }
    }

    private double GetCpuUsage()
    {
        currentProcess.Refresh();
        var startCpuTime = currentProcess.TotalProcessorTime;
        var startTime = DateTime.UtcNow;

        Thread.Sleep(10);

        currentProcess.Refresh();
        var endCpuTime = currentProcess.TotalProcessorTime;
        var endTime = DateTime.UtcNow;

        var cpuUsedMs = (endCpuTime - startCpuTime).TotalMilliseconds;
        var totalMsPassed = (endTime - startTime).TotalMilliseconds;

        return (cpuUsedMs / (totalMsPassed * Environment.ProcessorCount)) * 100;
    }
}