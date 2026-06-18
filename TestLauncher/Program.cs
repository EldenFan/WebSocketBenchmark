using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net.Http.Json;
using TestLauncher.Dto;

namespace TestLauncher
{
    class Program
    {
        private static HttpClient client = new();

        private static readonly List<int> clientsTestNumbers = [1, 10, 30, 50, 100, 500, 1000];

        static async Task Main(string[] args)
        {
            foreach (int i in clientsTestNumbers)
            {
                Console.WriteLine($"Количество клиентов: {i}");

                await TestShortPolling(i);

                await TestLongPolling(i);

                //await TestWebSocket(i);
            }

            Console.ReadKey();
        }

        private static async Task TestShortPolling(int clientsCount)
        {
            var results = new ConcurrentBag<TestResult>();

            var globalSw = Stopwatch.StartNew();

            var tasks = new List<Task>();
            int testDuration = 30;

            for (int i = 0; i < clientsCount; i++)
            {
                tasks.Add(Task.Run(async () =>
                {
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(testDuration));

                    while (!cts.Token.IsCancellationRequested)
                    {
                        try
                        {
                            var sw = Stopwatch.StartNew();

                            var response = await client.GetAsync("http://localhost:5000/api/shortPolling", cts.Token);

                            sw.Stop();

                            if (!response.IsSuccessStatusCode)
                            {
                                results.Add(new TestResult(sw.Elapsed.TotalMilliseconds, 0, false));

                                continue;
                            }

                            var data = await response.Content.ReadFromJsonAsync<Response>(cancellationToken: cts.Token);

                            if (data == null)
                                continue;

                            double deliveryLatency = (DateTime.Now - data.Timestamp).TotalMilliseconds;

                            results.Add(new TestResult(sw.Elapsed.TotalMilliseconds, deliveryLatency, true));
                        }
                        catch
                        {
                            results.Add(new TestResult(0, 0, false));
                        }

                        await Task.Delay(100);
                    }
                }));
            }

            await Task.WhenAll(tasks);

            globalSw.Stop();

            PrintStatistics("SHORT POLLING", results, globalSw.Elapsed.TotalSeconds);
        }

        private static async Task TestLongPolling(int clientsCount)
        {
            var results = new ConcurrentBag<TestResult>();

            var globalSw = Stopwatch.StartNew();

            var tasks = new List<Task>();
            int testDuration = 30;

            for (int i = 0; i < clientsCount; i++)
            {
                tasks.Add(Task.Run(async () =>
                {
                    ulong sequence = 0;

                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(testDuration));

                    while (!cts.Token.IsCancellationRequested)
                    {
                        try
                        {
                            var sw = Stopwatch.StartNew();

                            var response = await client.GetAsync($"http://localhost:5000/api/longPolling?lastSequence={sequence}", cts.Token);

                            sw.Stop();

                            if (!response.IsSuccessStatusCode)
                            {
                                results.Add(new TestResult(sw.Elapsed.TotalMilliseconds, 0, false));

                                continue;
                            }

                            var data = await response.Content.ReadFromJsonAsync<Response>(cancellationToken: cts.Token);

                            if (data == null)
                                continue;

                            sequence = data.Sequence;

                            double deliveryLatency = (DateTime.Now - data.Timestamp).TotalMilliseconds;

                            results.Add(new TestResult(sw.Elapsed.TotalMilliseconds, deliveryLatency, true));
                        }
                        catch
                        {
                            results.Add(new TestResult(0, 0, false));
                        }
                    }
                }));
            }

            await Task.WhenAll(tasks);

            globalSw.Stop();

            PrintStatistics("LONG POLLING", results, globalSw.Elapsed.TotalSeconds);
        }

        private static void PrintStatistics(string title, ConcurrentBag<TestResult> results, double durationSeconds)
        {
            int total = results.Count;
            int successful = results.Count(r => r.Success);

            double successRate = total == 0 ? 0 : successful * 100.0 / total;

            var successResults = results.Where(r => r.Success).ToList();

            double avgRequestTime = successResults.Count == 0 ? 0 : successResults.Average(r => r.RequestTime);

            double avgDeliveryLatency = successResults.Count == 0 ? 0 : successResults.Average(r => r.DeliveryLatency);

            double minDeliveryLatency = successResults.Count == 0 ? 0 : successResults.Min(r => r.DeliveryLatency);

            double maxDeliveryLatency = successResults.Count == 0 ? 0 : successResults.Max(r => r.DeliveryLatency);

            double rps = durationSeconds <= 0 ? 0 : total / durationSeconds;

            Console.WriteLine($"\n===== {title} =====");
            Console.WriteLine($"Всего запросов: {total}");
            Console.WriteLine($"Успешных: {successful} ({successRate:F2}%)");
            Console.WriteLine($"RPS: {rps:F2}");
            Console.WriteLine($"Среднее время HTTP-запроса: {avgRequestTime:F2} ms");
            Console.WriteLine($"Средняя задержка доставки: {avgDeliveryLatency:F2} ms");
            Console.WriteLine($"Мин задержка доставки: {minDeliveryLatency:F2} ms");
            Console.WriteLine($"Макс задержка доставки: {maxDeliveryLatency:F2} ms");
        }
    }
}