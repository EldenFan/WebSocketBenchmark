using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net.Http.Json;
using System.Net.WebSockets;
using System.Text.Json;
using TestLauncher.Dto;

namespace TestLauncher
{
    class Program
    {
        private static HttpClient client = new();

        private static readonly List<int> clientsTestNumbers = [1, 10, 30, 50, 100, 500, 1000];

        private static readonly string interfaceIndex = "8";
        private static readonly string serverPort = "5000";
        private static readonly int testDurationSec = 30;

        static async Task Main(string[] args)
        {
            foreach (int i in clientsTestNumbers)
            {
                Console.WriteLine($"Количество клиентов: {i}");

                await ExecuteTestWithCapture("SHORT_POLLING", () => TestShortPolling(i), i);
                await ExecuteTestWithCapture("LONG_POLLING", () => TestLongPolling(i), i);
                await ExecuteTestWithCapture("WEBSOCKET", () => TestWebSocket(i), i);
            }

            Console.ReadKey();
        }

        private static async Task TestShortPolling(int clientsCount)
        {
            var tasks = new List<Task>();

            for (int i = 0; i < clientsCount; i++)
            {
                tasks.Add(Task.Run(async () =>
                {
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(testDurationSec));

                    while (!cts.Token.IsCancellationRequested)
                    {
                        try
                        {
                            var response = await client.GetAsync("http://localhost:5000/api/shortPolling", cts.Token);
                        }
                        catch
                        {
                        }

                        await Task.Delay(100);
                    }
                }));
            }

            await Task.WhenAll(tasks);
        }

        private static async Task TestLongPolling(int clientsCount)
        {
            var tasks = new List<Task>();

            for (int i = 0; i < clientsCount; i++)
            {
                tasks.Add(Task.Run(async () =>
                {
                    ulong sequence = 0;
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(testDurationSec));

                    while (!cts.Token.IsCancellationRequested)
                    {
                        try
                        {
                            var response = await client.GetAsync($"http://localhost:5000/api/longPolling?lastSequence={sequence}", cts.Token);
                            var data = await response.Content.ReadFromJsonAsync<Response>(cancellationToken: cts.Token);
                            if (data == null) continue;
                            sequence = data.Sequence;
                        }
                        catch
                        {
                        }
                    }
                }));
            }

            await Task.WhenAll(tasks);
        }

        private static async Task TestWebSocket(int clientsCount)
        {
            JsonSerializerOptions options = new() { PropertyNameCaseInsensitive = true };
            var tasks = new List<Task>();

            for (int i = 0; i < clientsCount; i++)
            {
                tasks.Add(Task.Run(async () =>
                {
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(testDurationSec));
                    using var ws = new ClientWebSocket();

                    try
                    {
                        await ws.ConnectAsync(new Uri("ws://localhost:5000/api/ws"), cts.Token);
                        var buffer = new byte[4096];

                        while (ws.State == WebSocketState.Open && !cts.Token.IsCancellationRequested)
                        {
                            var result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);

                            if (result.MessageType == WebSocketMessageType.Close)
                            {
                                break;
                            }
                        }
                    }
                    catch
                    {
                    }
                }));
            }

            await Task.WhenAll(tasks);
        }

        private static async Task ExecuteTestWithCapture(string testName, Func<Task> testAction, int clients)
        {
            string capturesDirectory = Path.Combine(AppContext.BaseDirectory, "Captures");

            Directory.CreateDirectory(capturesDirectory);

            string pcapFile = Path.Combine(capturesDirectory, $"{testName.ToLower()}_{clients}_clients.pcap");

            var tsharkStartInfo = new ProcessStartInfo
            {
                FileName = "tshark.exe",
                Arguments = $"-i {interfaceIndex} -f \"tcp port {serverPort}\" -w {pcapFile} -q",
                CreateNoWindow = true,
                UseShellExecute = false
            };

            using var tsharkProcess = Process.Start(tsharkStartInfo);
            await Task.Delay(1500);

            Console.WriteLine($"[TShark] Сбор трафика для {testName} ({clients} кл.) -> {pcapFile}");

            await testAction();

            if (tsharkProcess != null && !tsharkProcess.HasExited)
            {
                tsharkProcess.Kill();
                await tsharkProcess.WaitForExitAsync();
            }

            if (File.Exists(pcapFile))
            {
                var fileInfo = new FileInfo(pcapFile);
                Console.WriteLine($"[Успешно] Файл записан. Размер сырого дампа: {fileInfo.Length / 1024.0:F2} КБ\n");
            }
        }
    }
}